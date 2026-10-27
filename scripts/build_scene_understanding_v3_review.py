"""Build the private V3 review from actual compiler/renderer outputs, no framework."""

import html
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path("review/scene-understanding-v3")
STYLE = """body{font:16px/1.5 system-ui;margin:24px;background:#f6f4ef;color:#26251f}main{max-width:1440px;margin:auto}a{color:#794f37}h1{line-height:1.15}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:9px;border:1px solid #d7d1c8;text-align:left}img{max-width:100%;height:auto;display:block}figure{margin:0;background:white;padding:12px;border-radius:12px}figcaption{margin-bottom:10px;font-weight:600}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:20px 0}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.note{background:#fff7e8;padding:16px;border-radius:10px}.scroll{overflow:auto}.tag{font:12px monospace}details{margin:14px 0}summary{cursor:pointer}pre{white-space:pre-wrap;font-size:12px}@media(max-width:700px){body{margin:12px}.grid,.cards{grid-template-columns:1fr}}"""  # noqa: E501


def picture(file: str, title: str) -> str:
    return f'<figure><figcaption>{html.escape(title)}</figcaption><img loading="lazy" src="{file}"></figure>'  # noqa: E501


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="fr"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{STYLE}</style><main>"
        f"<h1>{html.escape(title)}</h1>{body}</main></html>"
    )


def summary(values: list[float | None]) -> dict[str, float | int] | None:
    known = [v for v in values if v is not None]
    return (
        {
            "n": len(known),
            "median": float(np.median(known)),
            "p95": float(np.percentile(known, 95)),
            "max": max(known),
        }
        if known
        else None
    )


def main() -> None:
    matrix = json.loads((ROOT / "matrix-rendered.json").read_text("utf8"))
    live = (
        json.loads((ROOT / "live-benchmark.json").read_text("utf8"))
        if (ROOT / "live-benchmark.json").exists()
        else []
    )
    performance = []
    for key in sorted({(r["scene"], r["width"], r["height"]) for r in live}):
        runs = [r for r in live if (r["scene"], r["width"], r["height"]) == key]
        record = {"scene": key[0], "viewport": list(key[1:]), "runs": len(runs)}
        for field in ["displayMs", "firstResponseMs", "firstRenderMs", "finalMs"]:
            record[field] = {
                "firstRun": runs[0].get(field),
                "warm": summary([r.get(field) for r in runs[1:]]),
                "all": summary([r.get(field) for r in runs]),
            }
        record["preparedProductSwitchMs"] = summary(
            [r["switches"][i] for r in runs for i in [1, 3, 4] if len(r["switches"]) > i]
        )
        record["coldMaterialPreparationMs"] = summary(
            [r["switches"][i] for r in runs for i in [0, 2] if len(r["switches"]) > i]
        )
        record["modelWarmupMs"] = runs[0]["final"].get("modelWarmupMs")
        stages: dict[str, list[float | None]] = {}
        for run in runs:
            sources = [
                ("backend", run.get("analysisTimings", {})),
                ("semantic_and_fast", run.get("semanticTimings", {})),
                ("quality", run.get("final", {}).get("qualityStages", {})),
            ]
            for prefix, metrics in sources:
                for name, value in (metrics or {}).items():
                    if isinstance(value, (int, float)):
                        stages.setdefault(prefix + "." + name, []).append(float(value))
            for metric in (run.get("browserStages") or {}).get("lignes", []):
                stages.setdefault("browser.perRunMedian." + metric["nom"], []).append(
                    metric["mediane"]
                )
        record["stagesMs"] = {
            name: {"firstInCase": values[0], "warm": summary(values[1:]), "all": summary(values)}
            for name, values in stages.items()
        }
        performance.append(record)
    (ROOT / "performance.json").write_text(json.dumps(performance, indent=2), encoding="utf8")
    table = []
    cards = []
    for row in matrix:
        directory = ROOT / row["id"]
        renderer = row.get("renderer", {})
        has_scene = (directory / "quality.json").exists()
        has_final = (
            has_scene
            and not renderer.get("blocked", True)
            and (directory / "10-final.png").exists()
        )
        # A review judgement is not a calibrated model score or an automated PASS.
        scores = {
            s: ("PARTIAL" if has_final and s != "S6" else "NOT_EVALUABLE")
            for s in ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
        }
        row.update(scores)
        decision = row.get("decision", {}).get("decision", "MANUAL_REQUIRED")
        runtime = [r for r in performance if r["scene"] == row["id"] and r["viewport"][0] == 1440]
        first = (
            runtime[0]["firstRenderMs"]["all"]["median"]
            if runtime and runtime[0]["firstRenderMs"]["all"]
            else None
        )
        final = runtime[0]["finalMs"]["all"]["median"] if runtime else None
        row["timeToFirstRenderMs"] = first
        row["timeToFinalMs"] = final
        # Crop centres derive only from masks, never scene-specific corrective polygons.
        original = cv2.imread(str(directory / "01-original.png"))
        assert original is not None
        h, w = original.shape[:2]
        floor_image = cv2.imread(str(directory / "02-floor-mask.png"), 0)
        assert floor_image is not None
        floor = floor_image > 127
        blocked_image = cv2.imread(str(directory / "03-foreground-mask.png"), 0)
        assert blocked_image is not None
        blocked = blocked_image > 127
        visible = floor & ~blocked
        ys, xs = np.nonzero(visible)
        targets = {}
        if len(xs):
            for label, q in [("near-floor", 0.85), ("far-floor", 0.15)]:
                yy = int(np.quantile(ys, q))
                xx = np.nonzero(visible[yy])[0]
                if len(xx):
                    targets[label] = (int(np.median(xx)), yy)
            edge = visible & (cv2.dilate(blocked.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
            ey, ex = np.nonzero(edge)
            if len(ex):
                targets["wall-boundary"] = (int(ex[len(ex) // 3]), int(ey[len(ex) // 3]))
            contact = blocked & floor
            cy, cx = np.nonzero(contact)
            if len(cx):
                targets["object-contact"] = (int(cx[len(cx) // 2]), int(cy[len(cx) // 2]))
            distance = cv2.distanceTransform(contact.astype(np.uint8), cv2.DIST_L2, 3)
            ty, tx = np.nonzero(contact & (distance > 0) & (distance <= 2.2))
            if len(tx):
                targets["thin-leg"] = (int(tx[len(tx) // 2]), int(ty[len(tx) // 2]))
        if has_scene:
            scene = json.loads((directory / "quality.json").read_text("utf8"))
            rug = next((o for o in scene.get("occluders", []) if o.get("kind") == "rug"), None)
            if rug:
                point = rug["polygon"][len(rug["polygon"]) // 2]
                targets["rug-edge"] = (int(point["x"] * w), int(point["y"] * h))
        crops = []
        for name, (x, y) in targets.items():
            side = max(100, int(min(w, h) * 0.2))
            x0 = max(0, min(w - side, x - side // 2))
            y0 = max(0, min(h - side, y - side // 2))
            for variant, filename in [
                ("original", "01-original.png"),
                ("before", "before-final.png"),
                ("final", "10-final.png"),
            ]:
                image = (
                    cv2.imread(str(directory / filename))
                    if (directory / filename).exists()
                    else None
                )
                if image is not None:
                    cv2.imwrite(
                        str(directory / (name + "-" + variant + ".png")),
                        image[y0 : y0 + side, x0 : x0 + side],
                    )
            if has_final:
                crops.append(
                    "<h3>"
                    + name
                    + '</h3><div class="grid">'
                    + (
                        picture(name + "-before.png", "Avant V3")
                        if (directory / (name + "-before.png")).exists()
                        else picture(name + "-original.png", "Original : ancien rendu refusé")
                    )
                    + picture(name + "-final.png", "V3")
                    + "</div>"
                )
        intro = (
            f'<p><a href="../index.html">← Matrice</a> · <span class="tag">{decision}</span></p>'
        )
        intro += '<p class="note">Échelle indicative. Les statuts PARTIAL sont une revue technique prudente, pas une certification photoréaliste. Les crops sont proposés automatiquement depuis les masques ; leur nom ne valide pas la classe objet.</p>'  # noqa: E501
        if has_final:
            intro += (
                '<div class="grid">'
                + (
                    picture("before-final.png", "Analyse précédente — 8e03fea")
                    if (directory / "before-final.png").exists()
                    else picture(
                        "01-original.png", "Avant V3 : géométrie refusée, pas de parquet affiché"
                    )
                )
                + picture("10-final.png", "V3 — rendu réel, projection stable entre les passes")
                + "</div>"
            )
            intro += "<p>Cette vue de diagnostic montre aussi les scènes proposées à la correction. Le produit ne les auto-applique pas si la décision est MANUAL_REQUIRED.</p>"  # noqa: E501
        else:
            intro += '<p class="note">Pas de sol/plan exploitable : photo conservée et correction manuelle proposée. Grille, sol neutre et matériau final non évaluables ; aucun rendu de remplacement inventé.</p>'  # noqa: E501
        intro += picture("01-original.png", "Photo originale")
        diagnostics = [
            ("02-floor-mask.png", "Support physique du sol"),
            ("03-foreground-mask.png", "Matte de protection / exclusions"),
            ("04-room-layout.png", "Indices mur/sol"),
            ("05-camera-grid.png", "Grille métrique"),
            ("06-neutral-floor.png", "Sol neutre"),
            ("07-illumination.png", "Illumination basse fréquence"),
            ("08-contact-shadows.png", "Résidu sombre observé"),
            ("09-material-no-lighting.png", "Matériau sans lumière"),
        ]
        intro += (
            '<details><summary>Diagnostics</summary><div class="grid">'
            + "".join(picture(f, t) for f, t in diagnostics if (directory / f).exists())
            + "</div></details>"
        )
        intro += "<details><summary>Crops de contrôle</summary>" + "".join(crops) + "</details>"
        intro += (
            "<details><summary>Mesures et décision</summary><pre>"
            + html.escape(json.dumps(row, ensure_ascii=False, indent=2))
            + "</pre></details>"
        )
        (directory / "index.html").write_text(page(row["id"], intro), encoding="utf8")
        table.append(
            '<tr><td><a href="'
            + row["id"]
            + '/index.html">'
            + row["id"]
            + "</a></td>"
            + "".join("<td>" + scores[s] + "</td>" for s in scores)
            + f"<td>{decision}</td><td>{round(first) if first else '—'}</td><td>{round(final) if final else '—'}</td></tr>"  # noqa: E501
        )
        cards.append(
            '<a href="'
            + row["id"]
            + '/index.html">'
            + picture(
                row["id"] + ("/10-final.png" if has_final else "/01-original.png"),
                row["id"] + " · " + decision,
            )
            + "</a>"
        )
    body = '<p class="note">Revue privée locale · 13 scènes · aucune photo envoyée à une IA tierce. V3 automatise la séparation sol/objets et les deux passes. Le niveau visuel reste partiel, notamment aux contacts fins ; aucun résultat n’est certifié Roomvo-level.</p>'  # noqa: E501
    body += "<p>Les deux passes conservent la caméra/plan sur les 11 scènes compilables. Terrasse et photo très sombre sans plan : correction manuelle. Les calibrations du catalogue existant ne sont pas remplacées par cette matrice d’imports.</p>"  # noqa: E501
    body += (
        '<div class="scroll"><table><tr><th>Scène</th>'
        + "".join("<th>" + s + "</th>" for s in ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"])
        + "<th>Décision</th><th>Premier rendu, ms</th><th>Final, ms</th></tr>"
        + "".join(table)
        + "</table></div>"
    )
    body += "<p>Temps : médiane des vrais imports desktop, uniquement pour les cas mesurés. « — » = non mesuré. Les cinq compilations sur labels en cache sont séparées et ne sont pas des temps API.</p>"  # noqa: E501
    body += (
        "<details open><summary>Performances réelles et limites</summary><pre>"
        + html.escape(
            json.dumps(
                [{k: v for k, v in r.items() if k != "stagesMs"} for r in performance], indent=2
            )
        )
        + "</pre></details>"
    )
    body += (
        '<p><a href="performance.json">Mesures et distributions par étape</a> · '
        '<a href="lighting-stage-benchmark.json">Profil lumière / contacts</a> · '
        '<a href="live-benchmark.json">Vingt imports réels</a></p>'
    )
    body += '<div class="cards">' + "".join(cards) + "</div>"
    (ROOT / "index.html").write_text(page("Scene Understanding V3 — revue", body), encoding="utf8")
    (ROOT / "visual-matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf8")
    print("Review built:", len(matrix), "scenes;", len(performance), "live benchmark cases")


if __name__ == "__main__":
    main()

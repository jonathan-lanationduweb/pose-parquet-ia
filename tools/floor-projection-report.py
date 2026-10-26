"""Build the private review from actual paired captures; no synthetic result images."""

# ruff: noqa: E501 -- embedded HTML templates retain readable markup.
import html
import json
import statistics
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def project(
    point: list[float], camera: tuple[float, float, float, float, float]
) -> tuple[float, float]:
    cx, cy, focal, sx, sy = camera
    return ((cx + focal * point[0] / point[2]) * sx, (cy + focal * point[1] / point[2]) * sy)


root = Path("review/floor-projection-v3")
rows = json.loads((root / "matrix.json").read_text())["results"]
audit = json.loads((root / "audit.json").read_text())["rows"]
perf = (
    json.loads((root / "performance.json").read_text())["results"]
    if (root / "performance.json").exists()
    else []
)
labels = {
    "premibel-salon": "Salon canapé Premibel",
    "premibel-piano": "Piano et tapis",
    "chambre-parisienne": "Chambre",
    "chambre": "Pièce bleue",
    "piece-claire": "Grande pièce claire",
    "terrasse-mer": "Terrasse",
    "couloir": "Couloir",
    "appartement-ancien": "Appartement ancien",
    "owner": "Photo du propriétaire",
}
assessments = {
    "premibel-salon": ("better", "Proportions de la photo corrigées ; projection seule proche."),
    "premibel-piano": ("better", "Le piano et les lames ne sont plus étirés horizontalement."),
    "couloir": ("better", "Le motif est moins écrasé ; focale inférée encore incertaine."),
    "owner": (
        "same",
        "Dimensions des éléments corrigées, mais gain visuel insuffisant pour valider la mission.",
    ),
    "appartement-ancien": (
        "same",
        "Échelle rectifiée ; bandes de sol non couvertes toujours présentes dans le masque.",
    ),
    "chambre-parisienne": ("same", "Repère orthogonal, mais correction visuelle à faire relire."),
    "chambre": ("same", "Perspective presque inchangée, objets conservés."),
    "piece-claire": ("same", "Perspective presque inchangée, plinthes conservées."),
    "terrasse-mer": (
        "same",
        "Matériau extérieur conservé et dimensions physiques ; pas de gain de caméra établi.",
    ),
}
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
for row in rows:
    if row["variant"] != "v3" or row["canvas"]:
        continue
    image = Image.open(root / row["id"] / "03-grid-v3.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for p in row["projections"]:
        if not p or not p.get("camera"):
            continue
        c, plane = p["camera"], p["floorPlane"]
        cx, cy, f = c["principalPoint"]["x"], c["principalPoint"]["y"], c["focalLength"]
        sx, sy = w / (2 * cx), h / (2 * cy)
        nx, ny, nz = plane["normal"]

        h0 = (cy - f * nz / ny + nx / ny * cx) * sy
        h1 = (cy - f * nz / ny - nx / ny * (w / sx - cx)) * sy
        draw.line((0, h0, w, h1), fill="#ffcb28", width=3)
        for index, vp in enumerate(c["vanishingPoints"], 1):
            if abs(vp[2]) < 1e-9:
                continue
            x, y = vp[0] / vp[2] * sx, vp[1] / vp[2] * sy
            x, y = max(14, min(w - 70, x)), max(14, min(h - 30, y))
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), outline="#ffcb28", width=3)
            draw.text(
                (x + 10, y),
                f"VP{index}",
                font=font,
                fill="#ffcb28",
                stroke_width=1,
                stroke_fill="black",
            )
        origin = plane["originWorld"]

        if origin[2] > 0.05:
            a = project(origin, (cx, cy, f, sx, sy))
            draw.ellipse((a[0] - 5, a[1] - 5, a[0] + 5, a[1] + 5), fill="#ff6868")
            for name, axis, color in [
                ("U", plane["axisU"], "#ff6868"),
                ("V", plane["axisV"], "#65aaff"),
            ]:
                point = [x + y for x, y in zip(origin, axis, strict=True)]
                if point[2] > 0.05:
                    b = project(point, (cx, cy, f, sx, sy))
                    draw.line((*a, *b), fill=color, width=4)
                    draw.text(
                        b, name + " 1 m", font=font, fill=color, stroke_width=1, stroke_fill="black"
                    )
        draw.rectangle((12, 12, min(w - 12, 700), 88), fill="#17212a")
        draw.text((22, 20), p["status"] + " - hauteur supposee 1,50 m", fill="white", font=font)
        draw.text(
            (22, 48),
            "Grille : blanc 50 cm / vert 1 m - jaune : horizon et VP",
            fill="white",
            font=font,
        )
    image.save(root / row["id"] / "06-geometry-overlay.png")

metrics = []
for variant in ["legacy", "v3"]:
    for width in [1440, 390]:
        group = [r for r in perf if r["variant"] == variant and r["width"] == width]
        if group:
            rotations = [v for r in group for v in r["rotations"]]
            metrics.append(
                {
                    "variant": variant,
                    "width": width,
                    "rotationMedianMs": statistics.median(rotations),
                    "rotationMaxMs": max(rotations),
                    "cachedMedianMs": statistics.median(r["cachedMs"] for r in group),
                    "prefetchedMedianMs": statistics.median(r["prefetchedMs"] for r in group),
                }
            )
verdict = "FLOOR_PROJECTION_V3_NEEDS_WORK"
report = {
    "verdict": verdict,
    "publicRenderer": "legacy",
    "wallsEnabled": False,
    "visualMatrix": [
        {"scene": k, "assessment": v[0], "reason": v[1]} for k, v in assessments.items()
    ],
    "performance": metrics,
    "projectionMedianMs": statistics.median(r["projectionMs"] for r in audit),
    "refusedGeometry": [r["file"] for r in audit if r["status"] == "NEEDS_MANUAL_GEOMETRY"],
    "limits": [
        "Owner photo: visual gain not established; real dimension requested.",
        "No matched Roomvo result supplied.",
        "Public four-corner geometry fallback not implemented.",
        "V3 intentionally DEV-only; no general rollout.",
        "Canvas remains slower than WebGL.",
    ],
    "tests": [
        "Existing full Python suite PASS; three new floor-only tests PASS separately.",
        "Ruff PASS; mypy 68 files PASS.",
        "Product-concept, scene-engine, room-library, rooms-render-flow PASS.",
        "Product-reliability including 7 real uploads PASS.",
        "Boundary replay, compatibility/cache A/B/A, terrace/mobile/Canvas PASS.",
        "Occlusion pixel tests and 390x844 brush/undo/pinch PASS.",
        "Physical geometry, camera convergence, view inverse, 4608 actual GPU/Canvas UV probes PASS.",
    ],
}
(root / "report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
esc = html.escape
parts = [
    """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pose Parquet — projection V3</title><style>
body{font:16px/1.55 system-ui;margin:0;background:#f4f2ee;color:#282824}main{max-width:1500px;margin:auto;padding:32px}
h1{font-size:32px}h2{margin-top:40px}section{background:white;padding:24px;border-radius:16px;margin:24px 0}.note{background:#fff2d4;padding:20px;border-radius:14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}figure{margin:0;min-width:0}img{width:100%;height:auto;display:block;border-radius:8px}figcaption{padding:8px}a{color:#795236}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #ddd;padding:10px}details{margin:18px 0}code{word-break:break-word}nav{display:flex;flex-wrap:wrap;gap:14px}@media(max-width:650px){main{padding:12px}.grid{grid-template-columns:1fr}section{padding:12px}}
</style><main><h1>Placement du parquet : audit et prototype V3</h1>""",
    '<p class="note"><strong>'
    + verdict
    + "</strong><br>Le format des photos et le mode sol uniquement sont corrigés. V3 reste en DEV : le gain sur la photo du propriétaire n’est pas assez établi pour remplacer le renderer public.</p>",
    "<nav>" + "".join(f'<a href="#{k}">{esc(v)}</a>' for k, v in labels.items()) + "</nav>",
    "<section><h2>Pourquoi le rendu paraissait faux</h2><p>Le renderer utilisait déjà des mètres et une homographie. Le format 1200×800 imposé aux photos déformait les pièces verticales. Certains anciens plans avaient une échelle incompatible avec leur caméra. Les tuiles arrondissaient aussi les dimensions des éléments, notamment la longueur du bâton rompu.</p>",
    "<p>V3 utilise une caméra pinhole et un repère de sol orthonormé explicites ; les motifs ont leurs dimensions physiques avant projection. L’inverse de cette même projection sert à la rasterisation, sans autre warp. Ce repère est reconstruit depuis les estimations existantes : il ne constitue pas une nouvelle mesure indépendante de la pièce.</p>",
    "<p>Photo, masque, rendu, objets et pinceau utilisent le même ViewTransform. Les formats réels des photos sont conservés. Les murs sont retirés du parcours et leur post-traitement est désactivé ; le modèle multiclasses existant n’a pas été remplacé.</p>",
    "<p>La hauteur de caméra reste supposée à 1,50 m. La photo du salon n’a pas de mesure réelle ni de résultat Roomvo apparié. Une géométrie est refusée dans la bibliothèque complète et le nouveau guidage manuel à quatre coins reste à faire : la bascule générale est donc prématurée.</p></section>",
    "<section><h2>Mesures sur ce PC — Chrome headless</h2><p>Les durées ci-dessous sont des mesures réelles du navigateur, pas des promesses de performance sur un téléphone physique. Les textures sont préparées avant la mesure « préchargé ». Les temps d’analyse IA sont distincts.</p><table><tr><th>Moteur</th><th>Largeur</th><th>Rotation médiane / max</th><th>Frame en cache</th><th>Produit préchargé</th></tr>",
]
for m in metrics:
    parts.append(
        f"<tr><td>{m['variant']}</td><td>{m['width']}</td><td>{m['rotationMedianMs']:.1f} / {m['rotationMaxMs']:.1f} ms</td><td>{m['cachedMedianMs']:.1f} ms</td><td>{m['prefetchedMedianMs']:.1f} ms</td></tr>"
    )
parts.append(
    "</table><p>Construction du modèle de projection : médiane "
    + f"{report['projectionMedianMs']:.3f}"
    + " ms (100 répétitions/scène). Un draw call par zone ; pas de maillage CPU reconstruit à chaque angle.</p></section>"
)
for ident, label in labels.items():
    state, note = assessments[ident]
    parts.append(f'<section id="{ident}"><h2>{esc(label)} — {state}</h2><p>{esc(note)}</p>')
    for heading, files in [
        ("Rendu réel", ["04-legacy-render", "05-v3-render"]),
        ("Grille métrique", ["02-grid-current", "03-grid-v3"]),
    ]:
        parts.append(
            "<details"
            + (" open" if heading == "Rendu réel" else "")
            + "><summary>"
            + heading
            + '</summary><div class="grid">'
        )
        for name, caption in zip(files, ["Legacy", "V3"], strict=True):
            parts.append(
                f'<figure><a href="{ident}/{name}.png"><img loading="lazy" src="{ident}/{name}.png" alt="{esc(label)} {caption}"></a><figcaption>{caption}</figcaption></figure>'
            )
        parts.append("</div></details>")
    parts.append(
        f'<p><a href="{ident}/01-original.png">Original</a> · <a href="{ident}/06-geometry-overlay.png">Horizon, VP, origine et axes</a></p>'
    )
    for width in [1440, 390]:
        before = f"{ident}/07-viewport-before-{width}.png"
        after = f"{ident}/07-viewport-after-{width}.png"
        if (root / before).exists():
            parts.append(
                f'<details><summary>Correction du format dans l’interface — {width} px</summary><div class="grid"><figure><img loading="lazy" src="{before}"><figcaption>Avant : format imposé</figcaption></figure><figure><img loading="lazy" src="{after}"><figcaption>Après : proportions conservées</figcaption></figure></div></details>'
            )
    parts.append("</section>")
parts.append(
    "<section><h2>Vérifications</h2><ul>"
    + "".join("<li>" + esc(x) + "</li>" for x in report["tests"])
    + "</ul><p>Les captures sont privées, hors Git. Aucune photo utilisateur, poids de modèle ou référence concurrente n’est publiée.</p><p>Git : <code>feature/floor-projection-v3</code>. Aucun merge dans main, rebase ou force push.</p><p>Les ombres, quelques contours de mobilier et des bandes d’ancien sol demeurent à améliorer ; ils ne sont pas masqués par ce verdict.</p></section></main></html>"
)
(root / "index.html").write_text("".join(parts), encoding="utf-8")
print(verdict)
print(json.dumps(metrics, indent=2))

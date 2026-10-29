"""Loopback-only human foreground annotation; no model or production app imports."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

import numpy as np
from PIL import Image, ImageDraw

from scripts.foreground_proposals_v6 import ProposalBank, confirmed

SCHEMA = "pose-parquet-ai/human-foreground@1"
ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "datasets/private-real/foreground-v6"
SOURCES = ROOT / "review/foreground-mask-v5"
CATEGORIES = [
    "sofa",
    "table",
    "chair",
    "thin-leg",
    "rug",
    "low-cabinet",
    "radiator",
    "plant",
    "cable",
    "bed",
    "other-furniture",
    "small-object",
    "negative-region",
]
SCENES = {
    "sofa": "Salon — canapé, tapis, meuble bas",
    "thin-legs": "Salle à manger — table, chaises et pieds fins",
    "plant": "Chambre — lit, plante et objets au sol",
    "old-floor": "Bureau — câbles et mobilier",
    "rug": "Pièce avec tapis et plante",
    "empty-room": "Pièce vide — contrôle négatif",
    "empty": "Pièce claire — meuble bas et radiateur",
    "bright": "Cuisine — meubles bas",
    "dark": "Couloir sombre — contrôle négatif",
}


def number(value: Any, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("Coordonnée numérique requise")
    if not np.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError("Coordonnée hors image")
    return float(value)


def validate(payload: Any, scene: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("Format d'annotation inconnu")
    if payload.get("scene") != scene["id"] or payload.get("sourceSha256") != scene["sha256"]:
        raise ValueError("La photo ne correspond pas à ce relevé")
    w, h = scene["width"], scene["height"]
    if payload.get("width") != w or payload.get("height") != h:
        raise ValueError("Résolution source incorrecte")
    if payload.get("status") not in {"draft", "partial-reviewed", "reviewed-regions"}:
        raise ValueError("Statut invalide")
    author = payload.get("annotator", "")
    if not isinstance(author, str) or len(author) > 100:
        raise ValueError("Nom d'annotateur invalide")
    reviewed = payload["status"] == "reviewed-regions"
    if reviewed and (not author.strip() or payload.get("humanConfirmed") is not True):
        raise ValueError("Un nom et la confirmation de tracé humain sont requis")
    objects = payload.get("objects")
    if not isinstance(objects, list) or len(objects) > 100:
        raise ValueError("Liste d'objets invalide")
    if objects and payload.get("emptySceneConfirmed") is True:
        raise ValueError("Une scène déclarée vide ne peut pas contenir des objets")
    if reviewed and not objects and payload.get("emptySceneConfirmed") is not True:
        raise ValueError("Confirmez explicitement une scène sans objet")
    seen = set()
    for obj in objects:
        if not isinstance(obj, dict):
            raise ValueError("Objet invalide")
        ident = obj.get("id", "")
        if (
            not isinstance(ident, str)
            or not re.fullmatch(r"[a-z0-9-]{1,70}", ident)
            or ident in seen
        ):
            raise ValueError("Identifiant d'objet invalide ou dupliqué")
        seen.add(ident)
        if obj.get("category") not in CATEGORIES:
            raise ValueError("Catégorie invalide")
        if not isinstance(obj.get("notes", ""), str) or len(obj.get("notes", "")) > 2000:
            raise ValueError("Notes invalides")
        region = obj.get("region")
        if region is not None:
            if not isinstance(region, list) or len(region) != 4:
                raise ValueError("Zone examinée invalide")
            x0, y0, x1, y1 = [number(v, w if i % 2 == 0 else h) for i, v in enumerate(region)]
            if x1 <= x0 or y1 <= y0:
                raise ValueError("La zone doit avoir une surface positive")
        object_reviewed = confirmed(payload, obj)
        if (reviewed or object_reviewed) and (region is None or obj.get("reviewed") is not True):
            raise ValueError("Délimitez et relisez la zone de chaque objet")
        drawings = obj.get("drawings", [])
        if not isinstance(drawings, list) or len(drawings) > 5000:
            raise ValueError("Trop de tracés")
        for drawing in drawings:
            if not isinstance(drawing, dict):
                raise ValueError("Tracé invalide")
            if drawing.get("mode") not in {"foreground", "erase", "uncertain"}:
                raise ValueError("Mode de tracé invalide")
            if drawing.get("kind") not in {"brush", "polygon"}:
                raise ValueError("Outil de tracé invalide")
            number(drawing.get("radius"), max(w, h))
            points = drawing.get("points")
            if not isinstance(points, list) or not 1 <= len(points) <= 50000:
                raise ValueError("Points invalides")
            if drawing["kind"] == "polygon" and len(points) < 3:
                raise ValueError("Un polygone doit avoir au moins trois points")
            for point in points:
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError("Point invalide")
                number(point[0], w - 1)
                number(point[1], h - 1)
        mode = obj.get("annotationMode", "manual")
        if mode not in {"manual", "assisted-review"}:
            raise ValueError("Mode d'annotation invalide")
        if object_reviewed and (not author.strip() or obj.get("reviewed") is not True):
            raise ValueError("Une relecture humaine et un annotateur sont requis")
        if (
            (reviewed or object_reviewed)
            and obj["category"] != "negative-region"
            and not any(d["mode"] == "foreground" for d in drawings)
            and not (mode == "assisted-review" and obj.get("useProposal") is True)
        ):
            raise ValueError("Tracez ou utilisez une proposition avant de valider")
        if obj["category"] == "negative-region" and (
            obj.get("useProposal") or any(d["mode"] == "foreground" for d in drawings)
        ):
            raise ValueError("Une zone négative ne peut pas contenir de foreground")
    # Rebuild trusted fields; no arbitrary paths or extra files from the browser.
    return {
        k: payload.get(k)
        for k in [
            "schema",
            "scene",
            "sourceSha256",
            "width",
            "height",
            "status",
            "annotator",
            "humanConfirmed",
            "emptySceneConfirmed",
            "objects",
            "annotationMode",
        ]
    }


def masks(
    annotation: dict[str, Any], obj: dict[str, Any], base: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rasterize human source-pixel gestures; never predicts or grows an object."""
    w, h = annotation["width"], annotation["height"]
    # Rasterize at 2x and sample source pixel centres, without interpolation.
    # Pillow integer polygons alone include the far edge (one extra pixel).
    fg, uncertain = Image.new("L", (w * 2, h * 2)), Image.new("L", (w * 2, h * 2))
    if base is not None:
        if base.shape != (h, w):
            raise ValueError("La proposition doit garder la résolution source")
        fg = Image.fromarray(base.astype(np.uint8) * 255).resize(
            (w * 2, h * 2), Image.Resampling.NEAREST
        )
    for gesture in obj["drawings"]:
        target = uncertain if gesture["mode"] == "uncertain" else fg
        draw = ImageDraw.Draw(target)
        value = 0 if gesture["mode"] == "erase" else 255
        points = [(p[0] * 2, p[1] * 2) for p in gesture["points"]]
        if gesture["kind"] == "polygon":
            draw.polygon(points, fill=value)
        else:
            radius = max(0.5, gesture["radius"]) * 2
            draw.line(points, fill=value, width=max(1, round(radius * 2)))
            for x, y in points:
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=value)
        if gesture["mode"] == "erase":
            draw = ImageDraw.Draw(uncertain)
            if gesture["kind"] == "polygon":
                draw.polygon(points, fill=0)
            else:
                radius = max(0.5, gesture["radius"]) * 2
                draw.line(points, fill=0, width=max(1, round(radius * 2)))
                for x, y in points:
                    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=0)
    region = np.zeros((h, w), bool)
    if obj.get("region") is not None:
        x0, y0, x1, y1 = obj["region"]
        xx, yy = np.arange(w) + 0.5, np.arange(h) + 0.5
        region = ((yy >= y0) & (yy < y1))[:, None] & ((xx >= x0) & (xx < x1))[None, :]
    fg_pixels = np.asarray(fg)[1::2, 1::2] > 0
    uncertain_pixels = np.asarray(uncertain)[1::2, 1::2] > 0
    valid = region & ~uncertain_pixels
    return fg_pixels & valid, valid, uncertain_pixels


def store_record(
    data: dict[str, Any], scene: dict[str, Any], private: Path, bank: ProposalBank, lock: Any
) -> dict[str, Any]:
    """Only explicitly confirmed items are exported; other items stay drafts."""
    selected = [obj for obj in data["objects"] if confirmed(data, obj)]
    exports: list[tuple[str, bytes]] = []
    h, w = data["height"], data["width"]
    combined = np.zeros((h, w), bool)
    valid_all = np.zeros((h, w), bool)
    uncertain_all = np.zeros((h, w), bool)
    negative_domains = []
    # Resolve every assisted reference, including drafts, to reject stale masks.
    bases = {obj["id"]: bank.resolve(scene, obj) for obj in data["objects"]}
    for obj in selected:
        fg, valid, uncertain = masks(data, obj, bases[obj["id"]])
        negative = obj["category"] == "negative-region"
        if not valid.any() or (not negative and not fg.any()):
            raise ValueError("Objet ou région relue vide")
        if negative and fg.any():
            raise ValueError("Foreground dans une zone déclarée négative")
        minimum_background = max(4, int(np.ceil(valid.sum() * 0.02)))
        if not negative and int((valid & ~fg).sum()) < minimum_background:
            raise ValueError("Agrandissez la ROI et vérifiez aussi le vrai sol autour de l'objet")
        if negative:
            negative_domains.append(valid)
        obj["annotator"] = obj.get("annotator") or data["annotator"]
        obj["humanReviewed"] = True
        obj["humanConfirmed"] = True
        obj["annotationMode"] = obj.get("annotationMode", "manual")
        obj["proposalSource"] = (
            "foreground-v5-1" if obj["annotationMode"] == "assisted-review" else None
        )
        obj["humanDrawnFromScratch"] = obj["annotationMode"] == "manual"
        combined |= fg
        valid_all |= valid
        uncertain_all |= uncertain
        for suffix, array in [("foreground", fg), ("valid", valid), ("uncertain", uncertain)]:
            stream = io.BytesIO()
            Image.fromarray(array.astype(np.uint8) * 255).save(stream, format="PNG")
            exports.append((obj["id"] + "." + suffix + ".png", stream.getvalue()))
    empty = (
        data.get("status") == "reviewed-regions"
        and data.get("humanConfirmed") is True
        and data.get("emptySceneConfirmed") is True
        and not data["objects"]
    )
    if any((combined & negative & ~uncertain_all).any() for negative in negative_domains):
        raise ValueError("Une zone négative recouvre un objet déjà validé")
    if empty:
        valid_all[:] = True
    data["annotationMode"] = (
        "assisted-review"
        if any(o.get("annotationMode") == "assisted-review" for o in data["objects"])
        else "manual"
    )
    if selected or empty:
        combined &= ~uncertain_all
        valid_all &= ~uncertain_all
        for name, array in [
            ("foreground", combined),
            ("valid", valid_all),
            ("uncertain", uncertain_all),
        ]:
            stream = io.BytesIO()
            Image.fromarray(array.astype(np.uint8) * 255).save(stream, format="PNG")
            exports.append((name + ".png", stream.getvalue()))
        data["validatedObjectIds"] = [o["id"] for o in selected]
        data["status"] = (
            "reviewed-regions" if len(selected) == len(data["objects"]) else "partial-reviewed"
        )
        data["humanConfirmed"] = data["status"] == "reviewed-regions"
        data["maskHashes"] = {
            name: hashlib.sha256(content).hexdigest() for name, content in exports
        }
        data["scope"] = "reviewed-regions-only"
        data["maskRevision"] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    else:
        data.update(
            status="draft", maskRevision=None, scope="not-ground-truth", validatedObjectIds=[]
        )
    dest = private / scene["id"]
    with lock:
        dest.mkdir(parents=True, exist_ok=True)
        if exports:
            folder = dest / "revisions" / data["maskRevision"]
            folder.mkdir(parents=True, exist_ok=True)
            for name, content in exports:
                target = folder / name
                if not target.exists():
                    temporary = target.with_suffix(".tmp")
                    temporary.write_bytes(content)
                    temporary.replace(target)
        target = dest / "annotation.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
        temporary.replace(target)
    return data


class AnnotationServer(ThreadingHTTPServer):
    def __init__(
        self, address: tuple[str, int], sources: Path = SOURCES, private: Path = PRIVATE
    ) -> None:
        self.proposals = ProposalBank(sources)
        self.save_lock = Lock()
        from scripts.foreground_evaluation_v6 import EvaluationRunner

        output = (
            ROOT / "review/foreground-v6-phase2"
            if sources == SOURCES
            else private.parent / "evaluation"
        )
        self.evaluation = EvaluationRunner(private, sources, output)
        self.private = private
        self.photos: dict[str, Path] = {}
        self.scenes: dict[str, dict[str, Any]] = {}
        for ident, title in SCENES.items():
            photo = sources / ident / "01-original.png"
            if not photo.is_file():
                continue
            with Image.open(photo) as image:
                w, h = image.size
            self.photos[ident] = photo
            self.scenes[ident] = {
                "id": ident,
                "title": title,
                "width": w,
                "height": h,
                "sha256": hashlib.sha256(photo.read_bytes()).hexdigest(),
            }
        super().__init__(address, Handler)
        self.evaluation.queue()

    def server_close(self) -> None:
        super().server_close()
        self.evaluation.pool.shutdown(wait=False, cancel_futures=True)


class Handler(BaseHTTPRequestHandler):
    server: AnnotationServer

    def log_message(self, _format: str, *args: Any) -> None:
        pass

    def reply(self, status: int, body: bytes, mime: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.reply(403, b'{"error":"local host required"}')
            return
        path = urlparse(self.path).path
        assets = {
            "/": ("foreground-annotate.html", "text/html; charset=utf-8"),
            "/annotation.js": ("foreground-annotate.js", "text/javascript; charset=utf-8"),
            "/annotation.css": ("foreground-annotate.css", "text/css; charset=utf-8"),
        }
        if path in assets:
            name, mime = assets[path]
            self.reply(200, (ROOT / "tools" / name).read_bytes(), mime)
        elif path == "/api/manifest":
            self.reply(
                200,
                json.dumps(
                    {"scenes": list(self.server.scenes.values()), "categories": CATEGORIES}
                ).encode(),
            )
        elif path == "/api/evaluation":
            self.reply(200, json.dumps(self.server.evaluation.snapshot()).encode())
        elif path == "/api/evaluation/report":
            report = self.server.evaluation.output / "index.html"
            if self.server.evaluation.snapshot().get("status") != "complete":
                self.reply(409, b'{"error":"human GT pending or evaluation in progress"}')
            elif report.is_file():
                self.reply(200, report.read_bytes(), "text/html; charset=utf-8")
            else:
                self.reply(404, b'{"error":"not ready"}')
        elif path.startswith("/api/proposals/") and path[15:] in self.server.scenes:
            try:
                scene = self.server.scenes[path[15:]]
                self.reply(
                    200,
                    json.dumps(
                        {
                            "label": "PROPOSITION AUTOMATIQUE — NON VALIDÉE",
                            "proposals": self.server.proposals.public(scene),
                        },
                        ensure_ascii=False,
                    ).encode(),
                )
            except (OSError, ValueError) as error:
                self.reply(400, json.dumps({"error": str(error)}).encode())
        elif path.startswith("/photo/") and path[7:] in self.server.photos:
            self.reply(200, self.server.photos[path[7:]].read_bytes(), "image/png")
        elif path.startswith("/api/annotation/") and path[16:] in self.server.scenes:
            saved = self.server.private / path[16:] / "annotation.json"
            self.reply(200, saved.read_bytes() if saved.is_file() else b"null")
        else:
            self.reply(404, b'{"error":"not found"}')

    def do_POST(self) -> None:
        # Drain bounded request bodies before early rejection. Closing a Windows
        # socket with unread POST bytes can reset the connection before the
        # browser receives the useful 403 response.
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8_000_000:
                raise ValueError("Relevé trop volumineux")
            body = self.rfile.read(length)
        except ValueError as error:
            self.reply(400, json.dumps({"error": str(error)}).encode())
            return
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if self.headers.get("Origin") != origin or self.headers.get("Host") != origin[7:]:
            self.reply(403, b'{"error":"local origin required"}')
            return
        ident = urlparse(self.path).path.removeprefix("/api/annotation/")
        if not self.path.startswith("/api/annotation/") or ident not in self.server.scenes:
            self.reply(404, b'{"error":"not found"}')
            return
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("JSON requis")
            data = validate(json.loads(body), self.server.scenes[ident])
            saved = store_record(
                data,
                self.server.scenes[ident],
                self.server.private,
                self.server.proposals,
                self.server.save_lock,
            )
            self.server.evaluation.queue()
            self.reply(
                200,
                json.dumps({"saved": True, "status": saved["status"], "record": saved}).encode(),
            )
        except (ValueError, TypeError, KeyError, OSError) as error:
            self.reply(400, json.dumps({"error": str(error)}).encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = AnnotationServer(("127.0.0.1", args.port))
    if not server.scenes:
        raise SystemExit("Aucune photo privée V5 disponible ; aucune GT créée.")
    print(f"Annotation humaine : http://127.0.0.1:{server.server_port}", flush=True)
    print(
        "Données privées : datasets/private-real/foreground-v6 ; "
        "évaluation après validation humaine (5 objets / 3 catégories / 1 négatif).",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

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
]
SCENES = {
    "sofa": "Salon — canapé, tapis, meuble bas",
    "thin-legs": "Salle à manger — table, chaises et pieds fins",
    "empty": "Pièce claire — meuble bas et radiateur",
    "plant": "Chambre — lit, plante et objets au sol",
    "old-floor": "Bureau — câbles et mobilier",
    "rug": "Pièce avec tapis et plante",
    "bright": "Cuisine — meubles bas",
    "dark": "Couloir sombre — contrôle négatif",
    "empty-room": "Pièce vide — contrôle négatif",
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
    if payload.get("status") not in {"draft", "reviewed-regions"}:
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
        if reviewed and (region is None or obj.get("reviewed") is not True):
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
        if reviewed and not any(d["mode"] == "foreground" for d in drawings):
            raise ValueError("Tracez l'objet avant de valider")
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
        ]
    }


def masks(
    annotation: dict[str, Any], obj: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rasterize human source-pixel gestures; never predicts or grows an object."""
    w, h = annotation["width"], annotation["height"]
    # Rasterize at 2x and sample source pixel centres, without interpolation.
    # Pillow integer polygons alone include the far edge (one extra pixel).
    fg, uncertain = Image.new("L", (w * 2, h * 2)), Image.new("L", (w * 2, h * 2))
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


class AnnotationServer(ThreadingHTTPServer):
    def __init__(
        self, address: tuple[str, int], sources: Path = SOURCES, private: Path = PRIVATE
    ) -> None:
        self.save_lock = Lock()
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
            dest = self.server.private / ident
            dest.mkdir(parents=True, exist_ok=True)
            # Build the entire reviewed raster set before publishing anything.
            # Drafts never point at an older approved mask. Revision directories
            # are immutable, and the JSON pointer is replaced last.
            exports: list[tuple[str, bytes]] = []
            if data["status"] == "reviewed-regions":
                combined = np.zeros((data["height"], data["width"]), bool)
                reviewed_domain = np.zeros_like(combined)
                uncertain_all = np.zeros_like(combined)
                for obj in data["objects"]:
                    fg, valid, uncertain = masks(data, obj)
                    if not fg.any():
                        raise ValueError("Objet vide dans sa zone examinée")
                    combined |= fg
                    reviewed_domain |= valid
                    uncertain_all |= uncertain
                    for suffix, array in [
                        ("foreground", fg),
                        ("valid", valid),
                        ("uncertain", uncertain),
                    ]:
                        stream = io.BytesIO()
                        Image.fromarray(array.astype(np.uint8) * 255).save(stream, format="PNG")
                        exports.append((obj["id"] + "." + suffix + ".png", stream.getvalue()))
                if not data["objects"] and data.get("emptySceneConfirmed") is True:
                    reviewed_domain[:] = True
                combined &= ~uncertain_all
                reviewed_domain &= ~uncertain_all
                for name, array in [
                    ("foreground", combined),
                    ("valid", reviewed_domain),
                    ("uncertain", uncertain_all),
                ]:
                    stream = io.BytesIO()
                    Image.fromarray(array.astype(np.uint8) * 255).save(stream, format="PNG")
                    exports.append((name + ".png", stream.getvalue()))
                revision = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
                data["maskRevision"] = revision
                data["scope"] = "reviewed-regions-only"
            else:
                data["maskRevision"] = None
                data["scope"] = "not-ground-truth"
            with self.server.save_lock:
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
                temporary.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8"
                )
                temporary.replace(target)
            self.reply(200, json.dumps({"saved": True, "status": data["status"]}).encode())
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
    print("Données privées : datasets/private-real/foreground-v6 ; aucun modèle lancé.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

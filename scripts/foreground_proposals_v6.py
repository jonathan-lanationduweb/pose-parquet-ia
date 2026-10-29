"""Read-only V5.1 annotation suggestions. They are never ground truth by themselves."""

from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path
from threading import Lock
from typing import Any

import cv2
import numpy as np
from PIL import Image

# Verified against the installed ADE20K id2label config. UI suggestions only.
CATEGORY = {
    7: "bed",
    10: "low-cabinet",
    15: "table",
    17: "plant",
    19: "chair",
    23: "sofa",
    28: "rug",
    30: "chair",
    39: "small-object",
    64: "table",
    75: "chair",
    97: "other-furniture",
    146: "radiator",
    41: "small-object",
    57: "small-object",
    98: "small-object",
    112: "small-object",
    115: "small-object",
    125: "small-object",
    135: "small-object",
}


def confirmed(record: dict[str, Any], obj: dict[str, Any]) -> bool:
    return bool(
        obj.get("reviewed") is True
        and (
            obj.get("humanConfirmed") is True
            or (record.get("status") == "reviewed-regions" and record.get("humanConfirmed") is True)
        )
    )


class ProposalBank:
    def __init__(self, sources: Path) -> None:
        self.sources = sources
        self.baseline = sources.parent / "foreground-mask-v5-1"
        self.cache: dict[str, list[dict[str, Any]]] = {}
        self.lock = Lock()

    def entries(self, scene: dict[str, Any]) -> list[dict[str, Any]]:
        with self.lock:
            if scene["sha256"] not in self.cache:
                while len(self.cache) >= 3:
                    del self.cache[next(iter(self.cache))]
                self.cache[scene["sha256"]] = self._build(scene)
            return self.cache[scene["sha256"]]

    def _build(self, scene: dict[str, Any]) -> list[dict[str, Any]]:
        source = self.sources / scene["id"]
        final_path = self.baseline / scene["id"] / "v51.npy"
        if not final_path.is_file() or not (source / "labels.npy").is_file():
            return []
        final = np.load(final_path, allow_pickle=False).astype(bool)
        labels = np.load(source / "labels.npy", allow_pickle=False)
        h, w = scene["height"], scene["width"]
        if final.shape != (h, w) or labels.shape != (h, w):
            raise ValueError("Les propositions ne correspondent pas à la résolution photo")
        domain_path = source / "support.npy"
        domain = (
            np.load(domain_path, allow_pickle=False).astype(bool)
            if domain_path.is_file()
            else np.ones((h, w), bool)
        )
        if domain.shape != (h, w):
            raise ValueError("Domaine de propositions invalide")
        near_floor = cv2.dilate(domain.astype(np.uint8), np.ones((max(3, h // 4), 3), np.uint8)) > 0
        results = []
        for label, category in CATEGORY.items():
            count, components, stats, _ = cv2.connectedComponentsWithStats(
                ((labels == label) & final).astype(np.uint8), connectivity=8
            )
            for component in range(1, count):
                x, y, cw, ch, area = stats[component]
                if area < max(4, h * w // 100000):
                    continue
                coarse = components == component
                if not (coarse & near_floor).any():
                    continue
                # Keep original refined foreground, bounded to this semantic part.
                proposal = final & (
                    cv2.dilate(coarse.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
                )
                digest = hashlib.sha256(
                    scene["sha256"].encode() + str(label).encode() + proposal.tobytes()
                ).hexdigest()
                margin = max(12, round(max(cw, ch) * 0.12))
                region = [
                    max(0, int(x) - margin),
                    max(0, int(y) - margin),
                    min(w, int(x + cw) + margin),
                    min(h, int(y + ch) + margin),
                ]
                # Include a floor strip below high object parts (e.g. foliage),
                # so the human can inspect actual floor, not only the silhouette.
                floor_rows = np.flatnonzero(domain[:, region[0] : region[2]].any(axis=1))
                below = floor_rows[floor_rows >= int(y + ch)]
                if len(below):
                    region[3] = min(h, max(region[3], int(below[0]) + margin + 1))
                # Exact binary PNG cells, displayed at the original photo coordinates.
                py, px = np.nonzero(proposal)
                x0, x1 = int(px.min()), int(px.max()) + 1
                y0, y1 = int(py.min()), int(py.max()) + 1
                rgba = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
                rgba[:, :, :3] = 255
                rgba[:, :, 3] = proposal[y0:y1, x0:x1].astype(np.uint8) * 255
                stream = io.BytesIO()
                Image.fromarray(rgba).save(stream, format="PNG")
                results.append(
                    {
                        "id": "proposal-" + digest[:20],
                        "hash": digest,
                        "source": "foreground-v5-1",
                        "category": category,
                        "semanticClass": label,
                        "region": region,
                        "bounds": [x0, y0, x1, y1],
                        "png": "data:image/png;base64,"
                        + base64.b64encode(stream.getvalue()).decode(),
                        "mask": proposal,
                        "area": int(proposal.sum()),
                        "runs": self._runs(proposal),
                    }
                )
        return sorted(results, key=lambda p: -p["area"])[:80]

    @staticmethod
    def _runs(mask: np.ndarray) -> list[list[int]]:
        flat = np.pad(mask.reshape(-1).astype(np.int8), (1, 1))
        edges = np.diff(flat)
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        return [[int(a), int(b - a)] for a, b in zip(starts, ends, strict=True)]

    def public(self, scene: dict[str, Any]) -> list[dict[str, Any]]:
        return [{k: v for k, v in entry.items() if k != "mask"} for entry in self.entries(scene)]

    def resolve(self, scene: dict[str, Any], obj: dict[str, Any]) -> np.ndarray | None:
        ref = obj.get("proposal")
        if obj.get("annotationMode", "manual") == "manual":
            if ref:
                raise ValueError("Provenance automatique incompatible avec le mode manuel")
            return None
        if obj.get("annotationMode") != "assisted-review" or not isinstance(ref, dict):
            raise ValueError("Provenance de révision assistée requise")
        for entry in self.entries(scene):
            if (
                ref.get("id") == entry["id"]
                and ref.get("hash") == entry["hash"]
                and ref.get("source") == entry["source"]
            ):
                return entry["mask"].copy() if obj.get("useProposal") is True else None
        raise ValueError("Proposition absente, modifiée ou périmée")

# ruff: noqa: E501
"""Automatic preliminary evaluation of explicitly reviewed human regions only."""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
from PIL import Image

from app.services.foreground import OBJECT_CLASSES, RUG
from scripts.foreground_proposals_v6 import confirmed


def pixel_metrics(prediction: np.ndarray, truth: np.ndarray, valid: np.ndarray) -> dict[str, Any]:
    if prediction.shape != truth.shape or truth.shape != valid.shape:
        raise ValueError("Metric masks must share source dimensions")
    p, t, v = prediction.astype(bool), truth.astype(bool), valid.astype(bool)
    tp = int((p & t & v).sum())
    fp = int((p & ~t & v).sum())
    fn = int((~p & t & v).sum())
    return {
        "gtArea": tp + fn,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "validPixels": int(v.sum()),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "dice": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def classify(recall: float | None) -> str:
    if recall is None:
        return "NEGATIVE_REGION"
    return "NO_SEED" if recall < 0.1 else "GOOD_SEED" if recall >= 0.9 else "PARTIAL_SEED"


def fp_budget(
    before: np.ndarray, after: np.ndarray, truth: np.ndarray, valid: np.ndarray
) -> dict[str, Any]:
    added = after & ~before & valid
    tp = int((added & truth).sum())
    fp = int((added & ~truth).sum())
    return {
        "addedTP": tp,
        "addedFP": fp,
        "tpFpRatio": tp / fp if fp else None,
        "accepted": bool(tp > 0 and fp <= max(8, tp * 0.1)),
        "rule": "addedTP>0 and addedFP <= max(8, 10% addedTP); negatives must stay clean",
    }


def _png(path: Path, shape: tuple[int, int], expected_hash: str | None) -> np.ndarray:
    content = path.read_bytes()
    if expected_hash is not None and hashlib.sha256(content).hexdigest() != expected_hash:
        raise ValueError("GT mask hash mismatch")
    with Image.open(io.BytesIO(content)) as image:
        array = np.asarray(image)
    if array.shape != shape or array.dtype != np.uint8 or not np.isin(array, [0, 255]).all():
        raise ValueError("GT mask must be binary original-resolution grayscale PNG")
    return array > 0


def load_human(private: Path, sources: Path) -> tuple[list[dict[str, Any]], list[str]]:
    from scripts.foreground_annotation_v6 import masks, validate
    from scripts.foreground_proposals_v6 import ProposalBank

    bank = ProposalBank(sources)
    loaded = []
    errors = []
    if not private.is_dir():
        return [], []
    for file in sorted(private.glob("*/annotation.json")):
        try:
            raw = json.loads(file.read_text(encoding="utf8"))
            ident = file.parent.name
            if raw.get("scene") != ident:
                raise ValueError("Scene directory mismatch")
            photo = sources / ident / "01-original.png"
            photo_bytes = photo.read_bytes()
            with Image.open(io.BytesIO(photo_bytes)) as image:
                w, h = image.size
            scene = {
                "id": ident,
                "sha256": hashlib.sha256(photo_bytes).hexdigest(),
                "width": w,
                "height": h,
            }
            record = validate(raw, scene)
            objects = [o for o in record["objects"] if confirmed(record, o)]
            negative = (
                record.get("emptySceneConfirmed") is True
                and record.get("humanConfirmed") is True
                and raw.get("status") == "reviewed-regions"
            )
            if not objects and not negative:
                continue
            if not str(record.get("annotator", "")).strip():
                raise ValueError("Human annotator missing")
            revision = raw.get("maskRevision")
            if (
                not isinstance(revision, str)
                or len(revision) != 64
                or any(c not in "0123456789abcdef" for c in revision)
            ):
                raise ValueError("Current GT revision missing")
            folder = file.parent / "revisions" / revision
            hashes = raw.get("maskHashes", {})

            def read(
                name: str,
                folder: Path = folder,
                shape: tuple[int, int] = (h, w),
                hashes: dict[str, str] = hashes,
            ) -> np.ndarray:
                return _png(folder / (name + ".png"), shape, hashes.get(name + ".png"))

            global_fg, global_valid, global_uncertain = (
                read("foreground"),
                read("valid"),
                read("uncertain"),
            )
            if (global_valid & global_uncertain).any() or (global_fg & ~global_valid).any():
                raise ValueError("Inconsistent valid/uncertain GT")
            entries = []
            for obj in objects:
                fg, valid, uncertain = (
                    read(obj["id"] + ".foreground"),
                    read(obj["id"] + ".valid"),
                    read(obj["id"] + ".uncertain"),
                )
                # Legacy manual records have no hashes; recompute only their
                # stored human gestures, never a model prediction as substitute GT.
                if not hashes:
                    expected = masks(record, obj, bank.resolve(scene, obj))
                    for actual, wanted in zip([fg, valid, uncertain], expected, strict=True):
                        np.testing.assert_array_equal(actual, wanted)
                valid &= global_valid & ~global_uncertain & ~uncertain
                # Another annotated object is not a false positive for this object.
                valid &= ~(global_fg & ~fg)
                entries.append({"object": obj, "gt": fg & valid, "valid": valid})
            if negative:
                entries.append(
                    {
                        "object": {
                            "id": "explicit-empty-scene",
                            "category": "negative-region",
                            "annotationMode": "manual",
                            "notes": "Human-confirmed empty-scene control",
                        },
                        "gt": global_fg,
                        "valid": global_valid & ~global_uncertain,
                    }
                )
            loaded.append(
                {
                    "scene": ident,
                    "record": record,
                    "revision": revision,
                    "entries": entries,
                    "gt": global_fg,
                    "valid": global_valid & ~global_uncertain,
                    "source": photo,
                }
            )
        except (OSError, ValueError, KeyError, TypeError, AssertionError) as error:
            errors.append(file.parent.name + ": " + str(error))
    return loaded, errors


def readiness(loaded: list[dict[str, Any]]) -> dict[str, Any]:
    objects = [
        entry
        for scene in loaded
        for entry in scene["entries"]
        if entry["object"]["category"] != "negative-region"
    ]
    negative = [
        entry
        for scene in loaded
        for entry in scene["entries"]
        if entry["object"]["category"] == "negative-region" and entry["valid"].any()
    ]
    categories = sorted({e["object"]["category"] for e in objects})
    return {
        "objects": len(objects),
        "categories": categories,
        "negativeRegions": len(negative),
        "ready": len(objects) >= 5 and len(categories) >= 3 and len(negative) >= 1,
        "minimum": {"objects": 5, "categories": 3, "negativeRegions": 1},
    }


def _image_url(array: np.ndarray) -> str:
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()


def evaluate(
    loaded: list[dict[str, Any]], sources: Path, output: Path, local_runner: Any = None
) -> dict[str, Any]:
    from scripts.foreground_local_experiment_v6 import run_local

    output.mkdir(parents=True, exist_ok=True)
    rows = []
    experiments = []
    cards = []
    baseline_root = sources.parent / "foreground-mask-v5-1"
    all_budgets = []
    global_has_case_c = any(
        classify(
            pixel_metrics(
                np.isin(
                    np.load(sources / s["scene"] / "labels.npy", allow_pickle=False),
                    [*OBJECT_CLASSES, RUG],
                ),
                e["gt"],
                e["valid"],
            )["recall"]
        )
        == "NO_SEED"
        for s in loaded
        for e in s["entries"]
        if e["object"]["category"] != "negative-region"
    )
    for scene in loaded:
        ident = scene["scene"]
        src = sources / ident
        labels = np.load(src / "labels.npy", allow_pickle=False)
        coarse = np.isin(labels, [*OBJECT_CLASSES, RUG])
        baseline = np.load(baseline_root / ident / "v51.npy", allow_pickle=False).astype(bool)
        shape = scene["gt"].shape
        if coarse.shape != shape or baseline.shape != shape:
            raise ValueError("Baseline source dimensions do not match human GT")
        scene_rows = []
        for entry in scene["entries"]:
            cm = pixel_metrics(coarse, entry["gt"], entry["valid"])
            vm = pixel_metrics(baseline, entry["gt"], entry["valid"])
            obj = entry["object"]
            row = {
                "scene": ident,
                "object": obj["id"],
                "category": obj["category"],
                "annotationMode": obj.get("annotationMode", "manual"),
                "coarse": cm,
                "v5": vm,
                "case": classify(cm["recall"]),
                "notes": obj.get("notes", ""),
            }
            scene_rows.append((entry, row))
        with Image.open(scene["source"]) as image:
            rgb = np.asarray(image.convert("RGB"))
        result = None
        candidate = baseline.copy()
        control_only = all(row["case"] == "NEGATIVE_REGION" for _, row in scene_rows)
        if any(row["case"] == "NO_SEED" for _, row in scene_rows) or (
            global_has_case_c and any(row["case"] == "NEGATIVE_REGION" for _, row in scene_rows)
        ):
            # Human GT chooses which experiment is worth running, not its ROI.
            domain = np.load(src / "support.npy", allow_pickle=False).astype(bool)
            prior = np.load(baseline_root / ident / "prior.npy", allow_pickle=False).astype(bool)
            result = (local_runner or run_local)(rgb, domain, coarse, prior, baseline)
            candidate = result["candidateMask"]
            if candidate.shape != shape:
                raise ValueError("Candidate lost original image coordinates")
            budget = fp_budget(baseline, candidate, scene["gt"], scene["valid"])
            negative_clean = all(
                not ((candidate & ~baseline) & entry["valid"]).any()
                for entry, row in scene_rows
                if row["case"] == "NEGATIVE_REGION"
            )
            budget["negativeRegionsClean"] = negative_clean
            budget["controlOnly"] = control_only
            budget["accepted"] = (
                budget["addedFP"] == 0 if control_only else budget["accepted"]
            ) and negative_clean
            all_budgets.append(budget)
            experiments.append(
                {
                    "scene": ident,
                    "budget": budget,
                    **{k: v for k, v in result.items() if not isinstance(v, np.ndarray)},
                }
            )
        local_mask = result["additions"] | coarse if result else coarse
        seen = np.zeros(shape, np.uint8)
        if result:
            for call in result.get("calls", []):
                x0, y0, x1, y1 = call["box"]
                margin = max(2, (x1 - x0) // 32)
                seen[y0 + margin : y1 - margin, x0 + margin : x1 - margin] += 1
        raw_local = (
            (result.get("rawForeground", result["additions"]) | coarse) if result else coarse
        )
        for entry, row in scene_rows:
            row["local"] = pixel_metrics(local_mask, entry["gt"], entry["valid"])
            row["rawLocal"] = pixel_metrics(raw_local, entry["gt"], entry["valid"])
            area = int((entry["gt"] & entry["valid"]).sum())
            row["localObservationCoverage"] = (
                float(((seen >= 2) & entry["gt"] & entry["valid"]).sum() / area) if area else None
            )
            row["v6Candidate"] = pixel_metrics(candidate, entry["gt"], entry["valid"])
            row["delta"] = fp_budget(baseline, candidate, entry["gt"], entry["valid"])
            rows.append(row)
            # A crop is review material only; its GT rectangle never enters run_local.
            region = entry["object"].get("region", [0, 0, shape[1], shape[0]])
            x0, y0, x1, y1 = [int(x) for x in region]
            panels = []
            for title, mask in [
                ("Photo", None),
                ("Human-reviewed GT", entry["gt"]),
                ("Global", coarse),
                ("V5.1", baseline),
                ("Local candidate", local_mask),
                ("V6 candidate", candidate),
            ]:
                overlay = rgb.copy()
                if mask is not None:
                    selected = mask & entry["valid"]
                    overlay[selected] = (rgb[selected] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(
                        np.uint8
                    )
                panels.append(
                    "<figure><figcaption>"
                    + title
                    + '</figcaption><img loading="lazy" src="'
                    + _image_url(overlay[y0:y1, x0:x1])
                    + '"></figure>'
                )
            cards.append(
                "<section><h2>"
                + html.escape(ident + " / " + row["category"] + " / " + row["object"])
                + "</h2><p>"
                + html.escape(row["case"])
                + '</p><div class="panels">'
                + "".join(panels)
                + "</div></section>"
            )
    cases = {
        case: sum(r["case"] == case for r in rows)
        for case in ["GOOD_SEED", "PARTIAL_SEED", "NO_SEED", "NEGATIVE_REGION"]
    }
    improved = [
        r
        for r in rows
        if r["coarse"]["gtArea"] > 0 and r["v6Candidate"]["recall"] > r["v5"]["recall"]
    ]
    remaining = [
        r
        for r in rows
        if r["case"] == "NO_SEED"
        and (r["v6Candidate"]["recall"] or 0) < 0.1
        and (r["localObservationCoverage"] or 0) >= 0.9
        and (r["rawLocal"]["recall"] or 0) < 0.1
    ]
    verdict = "V6_PRELIMINARY_HUMAN_GT_ANALYZED"
    if len(improved) >= 2 and all_budgets and all(b["accepted"] for b in all_budgets):
        verdict = "V6_ONEFORMER_LOCAL_RECOVERY_VALIDATED"
    elif len(remaining) >= 2 and len({r["category"] for r in remaining}) >= 2 and experiments:
        verdict = "V6_SECOND_MODEL_EVALUATION_REQUIRED"
    categories = {}
    for category in sorted({row["category"] for row in rows}):
        subset = [row for row in rows if row["category"] == category]
        aggregate: dict[str, Any] = {
            "objects": len(subset),
            "caseCounts": {
                case: sum(row["case"] == case for row in subset)
                for case in ["GOOD_SEED", "PARTIAL_SEED", "NO_SEED", "NEGATIVE_REGION"]
            },
        }
        for stage in ["coarse", "v5", "local", "v6Candidate"]:
            aggregate[stage] = {}
            for metric in ["precision", "recall", "dice"]:
                values = [row[stage][metric] for row in subset if row[stage][metric] is not None]
                aggregate[stage][metric] = {
                    "mean": float(np.mean(values)) if values else None,
                    "median": float(np.median(values)) if values else None,
                    "worst": min(values) if values else None,
                }
        categories[category] = aggregate
    summary = {
        "byCategory": categories,
        "label": "PRELIMINARY HUMAN GT",
        "verdict": verdict,
        "readiness": readiness(loaded),
        "caseCounts": cases,
        "objects": rows,
        "localExperiments": experiments,
        "productionIntegrated": False,
        "confidenceCalibrated": False,
        "thresholds": {
            "NO_SEED": "recall < 0.10",
            "GOOD_SEED": "recall >= 0.90",
            "purpose": "analysis only; no product confidence calibration",
        },
        "limitation": "small, assisted-review-biased dataset; inspect red overlays; no new model downloaded",
    }
    (output / "metrics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8"
    )
    headings = [
        "Scene",
        "Object",
        "Category",
        "Case",
        "GT area",
        "Global P",
        "Global R",
        "V5 P",
        "V5 R",
        "Local P",
        "Local R",
        "V6 P",
        "V6 R",
        "Added TP",
        "Added FP",
    ]
    table_rows = []
    for row in rows:
        values = [
            row["scene"],
            row["object"],
            row["category"],
            row["case"],
            row["coarse"]["gtArea"],
        ]
        for stage in ["coarse", "v5", "local", "v6Candidate"]:
            values += [row[stage]["precision"], row[stage]["recall"]]
        values += [row["delta"]["addedTP"], row["delta"]["addedFP"]]
        table_rows.append(
            "<tr>"
            + "".join(
                "<td>"
                + html.escape(
                    "N/A"
                    if value is None
                    else f"{value:.3f}"
                    if isinstance(value, float)
                    else str(value)
                )
                + "</td>"
                for value in values
            )
            + "</tr>"
        )
    table = (
        '<div style="overflow:auto"><table border="1" cellpadding="6"><tr>'
        + "".join("<th>" + title + "</th>" for title in headings)
        + "</tr>"
        + "".join(table_rows)
        + "</table></div>"
    )
    doc = (
        '<!doctype html><meta charset="utf-8"><title>V6 preliminary human GT</title><style>body{font:15px system-ui;margin:24px;background:#f4f1eb}.panels{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}img{width:100%}figure{margin:0}section{background:white;padding:16px;margin:16px 0}pre{white-space:pre-wrap}@media(max-width:700px){.panels{grid-template-columns:repeat(2,minmax(0,1fr))}}</style><h1>PRELIMINARY HUMAN GT</h1><p>'
        + html.escape(verdict)
        + "</p><p>Only reviewed pixels, uncertain excluded. Assisted review is not a from-scratch human drawing. Local crops receive no GT. Candidate masks are not installed in production.</p>"
        + table
        + "".join(cards)
        + "<pre>"
        + html.escape(json.dumps(summary, ensure_ascii=False, indent=2))
        + "</pre>"
    )
    temporary = output / "index.tmp"
    temporary.write_text(doc, encoding="utf8")
    temporary.replace(output / "index.html")
    return summary


def gt_fingerprint(loaded: list[dict[str, Any]], sources: Path) -> str:
    """Ignore unapproved draft edits; rerun only for changed evaluated data."""
    items = []
    for scene in loaded:
        entries = []
        for entry in scene["entries"]:
            obj = entry["object"]
            entries.append(
                {
                    "id": obj["id"],
                    "category": obj["category"],
                    "annotationMode": obj.get("annotationMode", "manual"),
                    "notes": obj.get("notes", ""),
                    "gt": hashlib.sha256(entry["gt"].tobytes()).hexdigest(),
                    "valid": hashlib.sha256(entry["valid"].tobytes()).hexdigest(),
                }
            )
        files = [
            sources / scene["scene"] / "labels.npy",
            sources.parent / "foreground-mask-v5-1" / scene["scene"] / "v51.npy",
        ]
        items.append(
            {
                "scene": scene["scene"],
                "photo": scene["record"]["sourceSha256"],
                "entries": entries,
                "baselines": [hashlib.sha256(p.read_bytes()).hexdigest() for p in files],
            }
        )
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()


class EvaluationRunner:
    def __init__(self, private: Path, sources: Path, output: Path) -> None:
        self.private, self.sources, self.output = private, sources, output
        self.lock = Lock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="human-gt-evaluation")
        self.generation = 0
        self.running = False
        self.state: dict[str, Any] = {
            "status": "idle",
            "verdict": "V6_WAITING_FOR_HUMAN_GROUND_TRUTH",
            "objects": 0,
            "categories": [],
            "negativeRegions": 0,
        }
        self.completed_fingerprint: str | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return dict(json.loads(json.dumps(self.state)))

    def queue(self) -> None:
        with self.lock:
            self.generation += 1
            self.state = {**self.state, "status": "checking"}
            if self.running:
                return
            self.running = True
        self.pool.submit(self._work)

    def _work(self) -> None:
        while True:
            with self.lock:
                generation = self.generation
            try:
                loaded, errors = load_human(self.private, self.sources)
                gate = readiness(loaded)
                fingerprint = gt_fingerprint(loaded, self.sources)
                state = {
                    "status": "waiting",
                    "verdict": "V6_WAITING_FOR_HUMAN_GROUND_TRUTH",
                    **gate,
                    "errors": errors,
                }
                if gate["ready"] and not errors:
                    with self.lock:
                        self.state = {
                            **state,
                            "status": "evaluating",
                            "phase": "metrics / CASE A-B-C / local if NO_SEED",
                        }
                    if fingerprint != self.completed_fingerprint:
                        summary = evaluate(loaded, self.sources, self.output)
                        self.completed_fingerprint = fingerprint
                    else:
                        summary = json.loads(
                            (self.output / "metrics.json").read_text(encoding="utf8")
                        )
                    state.update(
                        status="complete",
                        verdict=summary["verdict"],
                        report="/api/evaluation/report",
                        caseCounts=summary["caseCounts"],
                        label=summary["label"],
                    )
            except Exception as error:
                state = {
                    "status": "error",
                    "verdict": "V6_PRELIMINARY_EVALUATION_FAILED",
                    "error": str(error),
                }
            with self.lock:
                if generation == self.generation:
                    self.state = state
                    self.running = False
                    return
                # A human edit supersedes an in-flight result. Re-evaluate the
                # latest immutable revision before publishing UI status.

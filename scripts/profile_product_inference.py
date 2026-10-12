"""Local CPU resolution/thread measurements; no ground-truth accuracy claims."""

import ctypes
import json
import os
import time
from ctypes import wintypes
from pathlib import Path

import cv2
import numpy as np
import torch

from app.services.floor_semantic import OneFormerFloor, environnement


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t)
        for name in (
            "PeakWorkingSetSize",
            "WorkingSetSize",
            "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage",
            "PagefileUsage",
            "PeakPagefileUsage",
            "PrivateUsage",
        )
    ]


def memory_mb() -> float | None:
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    okay = ctypes.windll.psapi.GetProcessMemoryInfo(
        wintypes.HANDLE(-1), ctypes.byref(counters), counters.cb
    )
    return counters.WorkingSetSize / 1024**2 if okay else None


out = Path("review/roomvo-v2")
out.mkdir(parents=True, exist_ok=True)
image = cv2.cvtColor(
    cv2.imread(os.environ.get("PPAI_PROFILE_PHOTO", "datasets/private-real/salon.jpg")),
    cv2.COLOR_BGR2RGB,
)
engine = OneFormerFloor()
t0 = time.perf_counter()
engine._charger()
load_ms = (time.perf_counter() - t0) * 1000
rows = []
for threads, sides in [(4, [640, 768, 896, 1024, 1280]), (1, [640]), (2, [640]), (8, [640])]:
    torch.set_num_threads(threads)
    for side in sides:
        os.environ["PPAI_INFERENCE_LONG_SIDE"] = str(side)
        for repeat in range(3 if side == 640 and threads == 4 else 1):
            r = engine.segment(image)
            mask = r.mask
            np.save(out / f"mask-{side}-{threads}.npy", mask)
            row = {
                "threads": threads,
                "side": side,
                "repeat": repeat,
                "timings": r.timings,
                "metadata": r.metadata,
            }
            row["rss_mb"] = memory_mb()
            rows.append(row)
            print(json.dumps(row), flush=True)
            (out / "inference-profile.json").write_text(
                json.dumps(
                    {"environment": environnement(), "load_ms": load_ms, "rows": rows}, indent=2
                )
            )
reference = np.load(out / "mask-1280-4.npy")
for row in rows:
    mask = np.load(out / f"mask-{row['side']}-{row['threads']}.npy")
    row["relative_iou_1280"] = float(
        np.logical_and(mask, reference).sum() / max(1, np.logical_or(mask, reference).sum())
    )
(out / "inference-profile.json").write_text(
    json.dumps(
        {
            "environment": environnement(),
            "load_ms": load_ms,
            "reference": "1280px prediction, NOT ground truth",
            "rows": rows,
        },
        indent=2,
    )
)

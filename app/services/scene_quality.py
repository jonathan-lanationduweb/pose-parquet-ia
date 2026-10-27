"""Conservative production decision; unknown confidence never means perfect."""

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class SceneDecision:
    decision: str
    reasons: list[str]
    quality: dict[str, float | None]


def scene_quality_gate(
    quality: dict[str, float | None],
    *,
    checks: dict[str, Any] | None = None,
    visual: dict[str, str] | None = None,
    image_rejected: bool = False,
) -> SceneDecision:
    checks = checks or {}
    visual = visual or {}
    reasons = []
    if (
        image_rejected
        or checks.get("non_finite")
        or any(v is not None and not math.isfinite(v) for v in quality.values())
    ):
        return SceneDecision("FAILED_GRACEFULLY", ["unusable_image_or_geometry"], quality)
    if visual.get("S1") == "FAIL" or visual.get("S2") == "FAIL" or visual.get("S4") == "BLOCKING":
        reasons.append("blocking_visual_evidence")
    if any(checks.values()):
        reasons.append("scene_validation_failed")
    for name, threshold in (
        ("floorQuality", 0.35),
        ("foregroundQuality", 0.35),
        ("cameraQuality", 0.2),
        ("scaleQuality", 0.2),
    ):
        score = quality.get(name)
        if score is not None and score < threshold:
            reasons.append(name + "_insufficient")
    if reasons:
        return SceneDecision("MANUAL_REQUIRED", reasons, quality)
    required = (
        "imageQuality",
        "floorQuality",
        "boundaryQuality",
        "layoutQuality",
        "cameraQuality",
        "scaleQuality",
        "foregroundQuality",
        "illuminationQuality",
    )
    uncertain = [k for k in required if (value := quality.get(k)) is None or value < 0.8]
    if uncertain:
        return SceneDecision("APPROXIMATE_RENDER", [k + "_unverified" for k in uncertain], quality)
    return SceneDecision("AUTO_RENDER", [], quality)

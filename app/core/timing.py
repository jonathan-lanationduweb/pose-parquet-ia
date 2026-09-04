"""Chronométrage des étapes du pipeline.

Le LOT 0 n'implémente que deux étages sur sept. Les cinq autres sont malgré
tout déclarés, à `None` : c'est ce qui permettra de comparer des modèles sans
changer le format de sortie, et de voir tout de suite quel étage coûte cher.

`None` veut dire « pas exécutée », `0.0` voudrait dire « instantanée ». La
distinction compte pour lire un benchmark.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter

#: Les étages du pipeline, dans l'ordre où ils s'exécuteront.
#: Voir docs/architecture.md et docs/roadmap.md.
STAGES: tuple[str, ...] = (
    "load_image",
    "quality_analysis",
    "lens_analysis",
    "segmentation",
    "depth",
    "perspective",
    "occlusion",
    "scene_builder",
)


@dataclass(slots=True)
class Timings:
    """Durées mesurées, en millisecondes, par nom d'étage."""

    stages: dict[str, float] = field(default_factory=dict)
    _started: float = field(default_factory=perf_counter)

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        """Chronomètre un bloc et l'enregistre sous `stage`.

        L'étage est enregistré même si le bloc lève : une étape qui échoue au
        bout de 4 secondes est une information, pas un trou.
        """
        if stage not in STAGES:
            raise ValueError(f"Étage inconnu : {stage!r}")
        start = perf_counter()
        try:
            yield
        finally:
            self.stages[stage] = round((perf_counter() - start) * 1000, 3)

    def as_dict(self) -> dict[str, float | None]:
        """Tous les étages, `None` pour ceux qui n'ont pas tourné, plus le total."""
        out: dict[str, float | None] = {f"{stage}_ms": self.stages.get(stage) for stage in STAGES}
        out["total_ms"] = round((perf_counter() - self._started) * 1000, 3)
        return out

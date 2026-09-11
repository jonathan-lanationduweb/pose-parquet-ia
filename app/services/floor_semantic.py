"""Candidats sémantiques ADE20K — OneFormer et UPerNet.

**EXPLORATOIRE. AUCUN CHOIX DE MODÈLE.**

Deux points d'accès, tous deux dans la grille de licences vérifiée
(`docs/MODEL-LICENSES.md` §3.1) :

| candidat | point d'accès | poids | code |
| --- | --- | --- | --- |
| OneFormer | `shi-labs/oneformer_ade20k_swin_*` | MIT (fiche de modèle) | MIT |
| UPerNet + ConvNeXt | `openmmlab/upernet-convnext-small` | MIT (fiche de modèle) | Apache-2.0 |

## Un écart à déclarer

`MODEL-LICENSES.md` cite MMSegmentation comme code d'UPerNet. Ici, c'est
l'implémentation de `transformers` qui exécute **les poids d'OpenMMLab** :
installer MMSegmentation demanderait la chaîne `mmcv`/`mim`, sa compilation et
son épinglage de version, pour un candidat qu'on n'a pas encore choisi. La
traçabilité tient : les poids sont ceux du point d'accès officiel d'OpenMMLab,
et `transformers` est l'implémentation de référence de ce point d'accès. Ce
n'est pas MMSegmentation, et le dire compte — un jour où les deux
divergeraient, c'est ici qu'il faudrait revenir.

## Processeur seulement

Aucun CUDA sur cette machine (vérifié, pas supposé). Tout tourne sur
processeur, ce qui fixe le régime : on mesure des secondes, pas des
millisecondes, et les temps ne se comparent qu'entre eux.

## Chargement paresseux

Un modèle se charge une fois par processus, pas une fois par requête : le
chargement domine tout le reste. Le cache est un dictionnaire de module —
suffisant ici, et honnêtement insuffisant pour un service à plusieurs
travailleurs, ce qui n'est pas le sujet de cette passe.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from app.services.floor_segmentation import (
    FloorSegmentationResult,
    clean_mask,
    mask_boundary,
    semantic_to_floor_visible,
)

#: Emplacement des poids. Hors de Git (`.gitignore` : `models/`).
CACHE_DIR = "models/hf-cache"

#: Points d'accès retenus. Un seul par famille : télécharger trois variantes
#: du même modèle coûterait des gigaoctets pour une comparaison qu'on ne
#: cherche pas ici.
CHECKPOINTS = {
    "oneformer": "shi-labs/oneformer_ade20k_swin_tiny",
    "upernet": "openmmlab/upernet-convnext-small",
}

_charges: dict[str, Any] = {}


def _torch() -> Any:
    import torch

    return torch


def environnement() -> dict[str, object]:
    """Ce que la machine offre réellement. Rien n'est supposé."""
    torch = _torch()
    return {
        "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "threads": int(torch.get_num_threads()),
    }


class OneFormerFloor:
    """OneFormer ADE20K : segmentation sémantique à 150 classes."""

    name = "oneformer-ade20k"

    def __init__(self, checkpoint: str | None = None) -> None:
        self.checkpoint = checkpoint or CHECKPOINTS["oneformer"]

    def _charger(self) -> tuple[Any, Any, float]:
        if self.checkpoint in _charges:
            return (*_charges[self.checkpoint], 0.0)
        from transformers import OneFormerForUniversalSegmentation, OneFormerProcessor

        t0 = time.perf_counter()
        processeur = OneFormerProcessor.from_pretrained(self.checkpoint, cache_dir=CACHE_DIR)
        modele = OneFormerForUniversalSegmentation.from_pretrained(
            self.checkpoint, cache_dir=CACHE_DIR
        )
        modele.eval()  # type: ignore[no-untyped-call]
        ms = (time.perf_counter() - t0) * 1000
        _charges[self.checkpoint] = (processeur, modele)
        return processeur, modele, ms

    def segment(self, image_rgb: np.ndarray) -> FloorSegmentationResult:
        from PIL import Image

        torch = _torch()
        processeur, modele, load_ms = self._charger()
        image = Image.fromarray(image_rgb)

        t0 = time.perf_counter()
        entrees = processeur(images=image, task_inputs=["semantic"], return_tensors="pt")
        with torch.no_grad():
            sorties = modele(**entrees)
        carte = processeur.post_process_semantic_segmentation(
            sorties, target_sizes=[image_rgb.shape[:2]]
        )[0]
        infer_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        labels = carte.cpu().numpy().astype(np.int32)
        masque = clean_mask(semantic_to_floor_visible(labels))
        bord = mask_boundary(masque)
        post_ms = (time.perf_counter() - t1) * 1000

        return FloorSegmentationResult(
            candidate=self.name,
            mask=masque,
            probability=None,
            boundary=bord,
            timings={
                "model_load": round(load_ms, 1),
                "inference": round(infer_ms, 1),
                "post": round(post_ms, 1),
                "total": round(load_ms + infer_ms + post_ms, 1),
            },
            metadata={
                "kind": "semantic",
                "learned": True,
                "checkpoint": self.checkpoint,
                "classes": "ADE20K 150",
                "adaptation": "floor(3) moins rug/carpet(28)",
                "inference_resolution": f"{image_rgb.shape[1]}x{image_rgb.shape[0]}",
                "labels_present": sorted({int(v) for v in np.unique(labels)}),
            },
        )


class UperNetFloor:
    """UPerNet + ConvNeXt, poids OpenMMLab, exécutés par `transformers`."""

    name = "upernet-convnext-ade20k"

    def __init__(self, checkpoint: str | None = None) -> None:
        self.checkpoint = checkpoint or CHECKPOINTS["upernet"]

    def _charger(self) -> tuple[Any, Any, float]:
        if self.checkpoint in _charges:
            return (*_charges[self.checkpoint], 0.0)
        from transformers import AutoImageProcessor, UperNetForSemanticSegmentation

        t0 = time.perf_counter()
        processeur = AutoImageProcessor.from_pretrained(  # type: ignore[no-untyped-call]
            self.checkpoint, cache_dir=CACHE_DIR
        )
        modele = UperNetForSemanticSegmentation.from_pretrained(
            self.checkpoint, cache_dir=CACHE_DIR
        )
        modele.eval()  # type: ignore[no-untyped-call]
        ms = (time.perf_counter() - t0) * 1000
        _charges[self.checkpoint] = (processeur, modele)
        return processeur, modele, ms

    def segment(self, image_rgb: np.ndarray) -> FloorSegmentationResult:
        from PIL import Image

        torch = _torch()
        processeur, modele, load_ms = self._charger()
        image = Image.fromarray(image_rgb)

        t0 = time.perf_counter()
        entrees = processeur(images=image, return_tensors="pt")
        with torch.no_grad():
            sorties = modele(**entrees)
        logits = torch.nn.functional.interpolate(
            sorties.logits, size=image_rgb.shape[:2], mode="bilinear", align_corners=False
        )
        probas = torch.softmax(logits, dim=1)[0]
        labels = probas.argmax(dim=0).cpu().numpy().astype(np.int32)
        infer_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        masque = clean_mask(semantic_to_floor_visible(labels))
        #: La probabilité de la classe `floor`, seule vraie confiance dont on
        #: dispose : elle vient du modèle, elle n'est pas fabriquée.
        proba_sol = probas[3].cpu().numpy().astype(np.float32)
        bord = mask_boundary(masque)
        post_ms = (time.perf_counter() - t1) * 1000

        return FloorSegmentationResult(
            candidate=self.name,
            mask=masque,
            probability=proba_sol,
            boundary=bord,
            timings={
                "model_load": round(load_ms, 1),
                "inference": round(infer_ms, 1),
                "post": round(post_ms, 1),
                "total": round(load_ms + infer_ms + post_ms, 1),
            },
            metadata={
                "kind": "semantic",
                "learned": True,
                "checkpoint": self.checkpoint,
                "classes": "ADE20K 150",
                "adaptation": "floor(3) moins rug/carpet(28)",
                "code": "transformers (poids OpenMMLab) — voir l'en-tête",
                "inference_resolution": f"{image_rgb.shape[1]}x{image_rgb.shape[0]}",
                "labels_present": sorted({int(v) for v in np.unique(labels)}),
            },
        )

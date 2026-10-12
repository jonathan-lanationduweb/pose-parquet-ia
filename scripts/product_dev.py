"""Démarrage local du visualiseur et de son analyse : python -m scripts.product_dev."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn


def main() -> None:
    """Active le preset dans ce processus seulement, toujours sur le loopback."""
    parser = argparse.ArgumentParser(description="Visualiseur Parquet — développement local")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--candidate",
        choices=("oneformer", "upernet", "opencv"),
        default=os.environ.get("PPAI_EXPERIMENTAL_FLOOR_CANDIDATE", "oneformer"),
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Le port doit être compris entre 1 et 65535.")
    # All weights are already installed on this workstation. Keep warmup independent
    # from Hub metadata requests; operators can opt out for initial installation.
    installed = Path("models/hf-cache/models--shi-labs--oneformer_ade20k_swin_tiny/snapshots")
    if args.candidate == "oneformer" and installed.exists():
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ["PPAI_DEV_SERVE_STATIC"] = "1"
    os.environ["PPAI_EXPERIMENTAL_FLOOR"] = "1"
    os.environ["PPAI_EXPERIMENTAL_FLOOR_WARMUP"] = "1"
    os.environ["PPAI_EXPERIMENTAL_FLOOR_CANDIDATE"] = args.candidate
    # Avoid oversized default thread pools on the development CPU. Configurable for deployment.
    print(f"Visualiseur : http://127.0.0.1:{args.port}/tools/product-concept.html", flush=True)
    print("L'analyse se prépare en arrière-plan ; choisissez déjà votre photo.", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

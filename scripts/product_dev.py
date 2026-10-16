"""Démarrage local du visualiseur et de son analyse : python -m scripts.product_dev."""

from __future__ import annotations

import argparse
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn


def port_is_available(port: int) -> bool:
    """Check before loading models; Windows must not share an occupied socket."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def is_product_server(port: int) -> bool:
    """Recognize our local service without using system proxies."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=2) as response:
            health = json.load(response)
        return bool(
            isinstance(health, dict)
            and health.get("service") == "pose-parquet-ai"
            and health.get("status") == "ok"
        )
    except (OSError, ValueError, urllib.error.URLError):
        return False


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
    if not port_is_available(args.port):
        if is_product_server(args.port):
            print("Le visualiseur est déjà démarré.", flush=True)
            print(
                f"Visualiseur : http://127.0.0.1:{args.port}/tools/product-concept.html", flush=True
            )
            print(
                "Après une modification Python, arrêtez la première instance avec Ctrl+C, "
                "puis relancez cette commande.",
                flush=True,
            )
            return
        parser.error(
            f"Le port {args.port} est occupé par un autre service. "
            f"Utilisez --port {args.port + 1 if args.port < 65535 else 8001}."
        )
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

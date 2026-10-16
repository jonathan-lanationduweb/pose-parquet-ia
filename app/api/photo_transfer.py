"""Pair a phone with one browser tab. No login, disk storage or permanent photos."""

import asyncio
import secrets
from dataclasses import dataclass
from io import BytesIO
from time import monotonic
from urllib.parse import urlsplit

import cv2
from fastapi import APIRouter, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

router = APIRouter(prefix="/v1/photo-transfers", tags=["photo-transfer"])
TTL_SECONDS = 600
MAX_SESSIONS = 32
MAX_BYTES = 10 * 1024 * 1024
MAX_STORED_BYTES = 64 * 1024 * 1024
NO_STORE = {"Cache-Control": "no-store"}


@dataclass
class Transfer:
    owner_key: str
    expires: float
    phone_url: str
    image: bytes | None = None


class TransferStore:
    """One worker's bounded, expiring mailbox. Deploy with session affinity."""

    def __init__(self) -> None:
        self.items: dict[str, Transfer] = {}
        self.uploading = 0

    def prune(self) -> None:
        now = monotonic()
        for token in list(self.items):
            if self.items[token].expires <= now:
                del self.items[token]

    def get(self, token: str, owner: str | None = None) -> Transfer:
        self.prune()
        item = self.items.get(token)
        if item is None or (
            owner is not None and not secrets.compare_digest(item.owner_key, owner)
        ):
            raise HTTPException(404, "Ce lien a expiré. Créez un nouveau QR code sur le PC.")
        return item

    async def cleanup(self) -> None:
        while True:
            await asyncio.sleep(30)
            self.prune()


class CreateTransfer(BaseModel):
    origin: str = Field(max_length=512)


def _store(request: Request) -> TransferStore:
    return request.app.state.photo_transfers  # type: ignore[no-any-return]


def _owner(request: Request) -> str:
    key = request.headers.get("X-Transfer-Key", "")
    if not key:
        raise HTTPException(404, "Transfert introuvable.")
    return key


def normalize_photo(data: bytes) -> bytes:
    """Verify bytes, orient the image and discard EXIF before relaying it."""
    try:
        with Image.open(BytesIO(data)) as original:
            if original.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(415, "Choisissez une photo JPEG, PNG ou WebP.")
            if original.width * original.height > 40_000_000:
                raise HTTPException(413, "Cette photo est trop grande.")
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
            out = BytesIO()
            image.save(out, format="JPEG", quality=92)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "Cette photo ne peut pas être lue.") from exc


@router.post("", status_code=201)
async def create_transfer(
    body: CreateTransfer, request: Request, response: Response
) -> dict[str, str | int]:
    try:
        parsed = urlsplit(body.origin)
        if parsed.hostname in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
            public = get_settings().public_url.strip().rstrip("/")
            if not public:
                raise HTTPException(
                    422, "L’adresse publique du simulateur doit être configurée pour le QR code."
                )
            parsed = urlsplit(public)
    except ValueError as exc:
        raise HTTPException(422, "Adresse du simulateur incorrecte.") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(422, "Adresse du simulateur incorrecte.")
    store = _store(request)
    store.prune()
    if len(store.items) >= MAX_SESSIONS:
        raise HTTPException(429, "Trop de transferts en attente. Réessayez dans un instant.")
    token, owner = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    phone_url = f"{parsed.scheme}://{parsed.netloc}/tools/phone-upload.html#{token}"
    store.items[token] = Transfer(owner, monotonic() + TTL_SECONDS, phone_url)
    response.headers.update(NO_STORE)
    return {"id": token, "ownerKey": owner, "phoneUrl": phone_url, "expiresIn": TTL_SECONDS}


@router.get("/{token}")
async def transfer_status(token: str, request: Request, response: Response) -> dict[str, str]:
    item = _store(request).get(token, _owner(request))
    item.expires = monotonic() + TTL_SECONDS
    response.headers.update(NO_STORE)
    return {"status": "ready" if item.image is not None else "waiting"}


@router.get("/{token}/qr.svg")
async def transfer_qr(token: str, request: Request) -> Response:
    item = _store(request).get(token, _owner(request))
    create_encoder = cv2.QRCodeEncoder_create  # type: ignore[attr-defined]
    matrix = await run_in_threadpool(lambda: create_encoder().encode(item.phone_url))
    size = matrix.shape[0]
    # Four extra quiet modules; pure vector output is sharp on all screen densities.
    cells = "".join(
        f"M{x + 4} {y + 4}h1v1h-1z"
        for y, row in enumerate(matrix)
        for x, value in enumerate(row)
        if value == 0
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size + 8} {size + 8}" '
        f'shape-rendering="crispEdges"><rect width="100%" height="100%" fill="white"/>'
        f'<path d="{cells}" fill="#242320"/></svg>'
    )
    return Response(svg, media_type="image/svg+xml", headers=NO_STORE)


@router.put("/{token}/photo", status_code=204)
async def upload_photo(token: str, request: Request) -> Response:
    store = _store(request)
    item = store.get(token)
    if item.image is not None:
        raise HTTPException(409, "La photo a déjà été envoyée.")
    if store.uploading >= 2:
        raise HTTPException(429, "Un autre transfert est en cours. Réessayez dans un instant.")
    store.uploading += 1
    try:
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BYTES:
                raise HTTPException(413, "Photo trop volumineuse (10 Mo maximum).")
            data.extend(chunk)
        normalized = await run_in_threadpool(normalize_photo, bytes(data))
        # Check again after the awaited decode: the owner may have cancelled or expired.
        item = store.get(token)
        if item.image is not None:
            raise HTTPException(409, "La photo a déjà été envoyée.")
        if (
            sum(len(x.image or b"") for x in store.items.values()) + len(normalized)
            > MAX_STORED_BYTES
        ):
            raise HTTPException(429, "Les transferts sont momentanément occupés. Réessayez.")
        item.image = normalized
    finally:
        store.uploading -= 1
    return Response(status_code=204, headers=NO_STORE)


@router.get("/{token}/photo")
async def receive_photo(token: str, request: Request) -> Response:
    item = _store(request).get(token, _owner(request))
    if item.image is None:
        return Response(status_code=204, headers=NO_STORE)
    return Response(item.image, media_type="image/jpeg", headers=NO_STORE)


@router.delete("/{token}", status_code=204)
async def delete_transfer(token: str, request: Request) -> Response:
    store = _store(request)
    store.get(token, _owner(request))
    del store.items[token]
    return Response(status_code=204, headers=NO_STORE)

"""Healthz APIs."""

from fastapi import APIRouter

router = APIRouter(prefix="/healthz", tags=["Monitoring APIs"])


@router.get("")
async def healthz() -> str:
    """Healthz API."""
    return "OK"

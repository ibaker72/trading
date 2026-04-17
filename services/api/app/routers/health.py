from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/config")
def config() -> dict[str, bool]:
    settings = get_settings()
    return {"demo_mode": settings.demo_mode}

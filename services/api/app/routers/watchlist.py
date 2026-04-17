from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WatchlistItem

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    symbol: str
    asset_class: str = "stock"


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    asset_class: str
    is_active: bool
    added_at: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[WatchlistItemResponse])
def list_watchlist(db: Session = Depends(get_db)) -> list[WatchlistItem]:
    return db.query(WatchlistItem).filter(WatchlistItem.is_active == True).order_by(WatchlistItem.asset_class, WatchlistItem.symbol).all()  # noqa: E712


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def add_symbol(req: WatchlistAddRequest, db: Session = Depends(get_db)) -> WatchlistItem:
    symbol = req.symbol.upper().strip()
    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.symbol == symbol, WatchlistItem.asset_class == req.asset_class)
        .first()
    )
    if existing:
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    item = WatchlistItem(symbol=symbol, asset_class=req.asset_class)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{symbol}", status_code=status.HTTP_200_OK)
def remove_symbol(symbol: str, db: Session = Depends(get_db)) -> dict:
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.symbol == symbol.upper(), WatchlistItem.is_active == True)  # noqa: E712
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Symbol not in watchlist")
    item.is_active = False
    db.commit()
    return {"ok": True}

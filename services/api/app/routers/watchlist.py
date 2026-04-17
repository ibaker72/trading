from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WatchlistItem

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    symbol: str
    asset_class: str


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    asset_class: str
    is_active: bool
    added_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[WatchlistItemResponse])
def get_watchlist(db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).filter(WatchlistItem.is_active == True).all()  # noqa: E712
    return [
        WatchlistItemResponse(
            id=item.id,
            symbol=item.symbol,
            asset_class=item.asset_class,
            is_active=item.is_active,
            added_at=item.added_at.isoformat(),
        )
        for item in items
    ]


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def add_watchlist_symbol(body: WatchlistAddRequest, db: Session = Depends(get_db)):
    if body.asset_class not in ("stock", "crypto"):
        raise HTTPException(status_code=400, detail="asset_class must be 'stock' or 'crypto'")

    symbol = body.symbol.strip().upper()
    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.symbol == symbol, WatchlistItem.asset_class == body.asset_class)
        .first()
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
            db.refresh(existing)
        return WatchlistItemResponse(
            id=existing.id,
            symbol=existing.symbol,
            asset_class=existing.asset_class,
            is_active=existing.is_active,
            added_at=existing.added_at.isoformat(),
        )

    item = WatchlistItem(symbol=symbol, asset_class=body.asset_class, is_active=True)
    db.add(item)
    db.commit()
    db.refresh(item)
    return WatchlistItemResponse(
        id=item.id,
        symbol=item.symbol,
        asset_class=item.asset_class,
        is_active=item.is_active,
        added_at=item.added_at.isoformat(),
    )


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def remove_watchlist_symbol(symbol: str, asset_class: str = "stock", db: Session = Depends(get_db)):
    sym = symbol.strip().upper()
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.symbol == sym, WatchlistItem.asset_class == asset_class)
        .first()
    )
    if item:
        item.is_active = False
        db.commit()

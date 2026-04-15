from fastapi import FastAPI

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, health, markets, paper, risk, strategies

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(markets.router)
app.include_router(strategies.router)
app.include_router(risk.router)
app.include_router(paper.router)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, health, markets, paper, risk, strategies
from app.routers import broker, scanner, bot

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    from app.bot.scheduler import start_scheduler
    start_scheduler(app)


@app.on_event("shutdown")
def shutdown() -> None:
    from app.bot.scheduler import stop_scheduler
    stop_scheduler(app)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(markets.router)
app.include_router(strategies.router)
app.include_router(risk.router)
app.include_router(paper.router)
app.include_router(broker.router)
app.include_router(scanner.router)
app.include_router(bot.router)

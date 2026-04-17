from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, health, markets, paper, risk, strategies
from app.routers import broker, scanner, bot, analytics, notifications as notifications_router
from app.routers import ws as ws_router
from app.routers import backtest as backtest_router
from app.routers import watchlist as watchlist_router

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    from app.database import SessionLocal
    from app.bot.state import rehydrate
    from app.demo_seeder import seed_demo_data, seed_initial_watchlist

    db = SessionLocal()
    try:
        rehydrate(db)
        seed_initial_watchlist(db)
        if settings.demo_mode:
            seed_demo_data(db)
    finally:
        db.close()

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
app.include_router(analytics.router)
app.include_router(notifications_router.router)
app.include_router(ws_router.router)
app.include_router(backtest_router.router)
app.include_router(watchlist_router.router)

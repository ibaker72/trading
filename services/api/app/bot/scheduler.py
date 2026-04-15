import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler(app) -> None:
    global _scheduler
    from app.config import get_settings
    from app.database import SessionLocal
    from app.bot.engine import TradingBotEngine

    settings = get_settings()
    engine = TradingBotEngine(db_session_factory=SessionLocal, settings=settings)

    _scheduler = BackgroundScheduler(timezone="UTC")

    def _run_cycle_job():
        from app.database import SessionLocal as _SessionLocal
        db = _SessionLocal()
        try:
            engine.run_cycle(db)
        except Exception as exc:
            logger.error("Scheduler job error: %s", exc)
        finally:
            db.close()

    _scheduler.add_job(
        _run_cycle_job,
        "interval",
        seconds=settings.scan_interval_seconds,
        id="trading_bot_cycle",
        replace_existing=True,
    )

    try:
        _scheduler.start()
        logger.info("Trading bot scheduler started (interval=%ds)", settings.scan_interval_seconds)
    except Exception as exc:
        logger.error("Failed to start scheduler: %s", exc)

    app.state.scheduler = _scheduler


def stop_scheduler(app) -> None:
    global _scheduler
    sched = getattr(app.state, "scheduler", None) or _scheduler
    if sched and sched.running:
        try:
            sched.shutdown(wait=False)
            logger.info("Trading bot scheduler stopped")
        except Exception as exc:
            logger.error("Error stopping scheduler: %s", exc)

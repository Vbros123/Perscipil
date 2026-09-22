"""Run supervised: PYTHONPATH=. python scripts/run_worker.py [--once]."""

import argparse, asyncio, logging, signal, time
from services.jobs import run_cycle
from services.workspace_monitoring import tick
from services.notifications import deliver_due
from core.config import get_settings
from core.observability import configure_logging


async def main(once=False):
    configure_logging()
    get_settings().validate_runtime()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    while not stop.is_set():
        started = time.monotonic()
        try:
            scheduled = tick()
            processed = await run_cycle()
            delivered = await deliver_due()
            logging.getLogger("privatelens.worker").info(
                "worker_cycle scheduled=%d processed=%d delivered=%d duration_ms=%d",
                scheduled,
                processed,
                delivered,
                int((time.monotonic() - started) * 1000),
            )
        except Exception:
            logging.getLogger("privatelens.worker").error(
                "worker_cycle_failed", exc_info=False
            )
            if once:
                raise
        if once:
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=5)
        except TimeoutError:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    asyncio.run(main(parser.parse_args().once))

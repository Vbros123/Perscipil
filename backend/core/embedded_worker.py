"""Optional worker sharing the web service's compute and sleep lifecycle."""

import asyncio
from contextlib import asynccontextmanager, suppress
import logging
from pathlib import Path
import sys

logger = logging.getLogger("privatelens.worker.supervisor")
BACKEND_ROOT = Path(__file__).resolve().parents[1]


async def stop_process(process, timeout=20):
    """Drain on SIGTERM, then reap even a child that ignores shutdown."""
    if process.returncode is not None:
        await process.wait()
        return
    with suppress(ProcessLookupError):
        process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except TimeoutError:
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()


@asynccontextmanager
async def embedded_worker(command=None, restart_delay=5, shutdown_timeout=20):
    """Supervise a separate process so synchronous jobs cannot block HTTP.

    The database queue and leases survive service sleep/restarts. This does not
    keep a free service awake or promise delivery at a fixed wall-clock time.
    """
    command = command or [sys.executable, "-m", "scripts.run_worker"]
    process = await asyncio.create_subprocess_exec(*command, cwd=BACKEND_ROOT)

    async def supervise():
        nonlocal process
        delay = restart_delay
        while True:
            code = await process.wait()
            logger.error("embedded_worker_exited code=%s retry_seconds=%s", code, delay)
            await asyncio.sleep(delay)
            try:
                process = await asyncio.create_subprocess_exec(*command, cwd=BACKEND_ROOT)
                logger.info("embedded_worker_restarted")
            except OSError:
                logger.error("embedded_worker_spawn_failed")
            delay = min(delay * 2, 60)

    task = asyncio.create_task(supervise())
    logger.info("embedded_worker_started mode=while_service_awake")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await stop_process(process, timeout=shutdown_timeout)
        logger.info("embedded_worker_stopped")

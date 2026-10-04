import asyncio
import sys

from core.embedded_worker import embedded_worker, stop_process


def test_child_is_restarted_and_stops_with_web_service(tmp_path):
    marker = tmp_path / "starts"
    script = (
        "from pathlib import Path; import time; "
        f"p=Path({str(marker)!r}); "
        "n=int(p.read_text()) if p.exists() else 0; p.write_text(str(n+1)); "
        "time.sleep(0.02)"
    )

    async def scenario():
        async with embedded_worker([sys.executable, "-c", script], restart_delay=0.01):
            async with asyncio.timeout(5):
                while not marker.exists() or int(marker.read_text() or "0") < 2:
                    await asyncio.sleep(0.01)
        starts = marker.read_text()
        await asyncio.sleep(0.1)
        assert marker.read_text() == starts

    asyncio.run(scenario())


def test_uncooperative_child_is_killed_and_reaped(tmp_path):
    marker = tmp_path / "ready"
    script = (
        "import signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"Path({str(marker)!r}).touch(); time.sleep(30)"
    )

    async def scenario():
        process = await asyncio.create_subprocess_exec(sys.executable, "-c", script)
        try:
            async with asyncio.timeout(5):
                while not marker.exists():
                    await asyncio.sleep(0.01)
            await stop_process(process, timeout=0.02)
            assert process.returncode is not None
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    asyncio.run(scenario())

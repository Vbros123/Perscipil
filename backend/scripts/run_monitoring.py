"""Run from backend: PYTHONPATH=. python scripts/run_monitoring.py; schedule hourly."""
import asyncio
from services.monitoring import run_due
if __name__ == '__main__':
    print({'processed': asyncio.run(run_due())})

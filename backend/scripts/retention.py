"""Run daily. Purge research content on configured schedule; preserve control history."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, update
from core.config import get_settings
from core.database import SessionLocal
from models.company import CompanyReport,CompanySearch
from models.workflows import Batch,BatchItem,MonitorEvent,Subscription,RateBucket

def purge():
    settings=get_settings()
    cutoff=datetime.now(timezone.utc)-timedelta(days=settings.REPORT_RETENTION_DAYS)
    with SessionLocal.begin() as db:
        db.execute(delete(CompanyReport).where(CompanyReport.created_at<cutoff))
        db.execute(delete(CompanySearch).where(CompanySearch.created_at<cutoff))
        db.execute(delete(Batch).where(Batch.created_at<cutoff))
        db.execute(delete(MonitorEvent).where(MonitorEvent.created_at<cutoff))
        # Monitoring only keeps the most recent weekly summary. Overdue subscriptions are cleared.
        db.execute(update(Subscription).where(Subscription.next_run<cutoff).values(previous=None))
        db.execute(delete(RateBucket).where(RateBucket.window<int(datetime.now(timezone.utc).timestamp())//60-1440))
if __name__=='__main__':purge()

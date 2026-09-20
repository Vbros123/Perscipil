"""Trusted operator command; every review is appended, never auto-approved."""
import argparse
from datetime import datetime, timezone
from core.database import SessionLocal
from models.workflows import Correction
p=argparse.ArgumentParser();p.add_argument('id',type=int);p.add_argument('--reviewer',required=True);p.add_argument('--status',choices=['under_review','resolved','rejected'],required=True);p.add_argument('--notes',required=True);p.add_argument('--corrected-snapshot')
a=p.parse_args()
with SessionLocal.begin() as db:
    row=db.get(Correction,a.id,with_for_update=True)
    if row is None:raise SystemExit('Correction not found')
    row.review_history=[*row.review_history,{'at':datetime.now(timezone.utc).isoformat(),'reviewer':a.reviewer,'status':a.status,'notes':a.notes,'corrected_snapshot':a.corrected_snapshot}]
    row.status=a.status

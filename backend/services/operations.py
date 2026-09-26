"""Aggregate metrics expose no tenant identifiers or provider payloads."""
from sqlalchemy import select, func
from core.database import SessionLocal
from models.organizations import WorkJob, Delivery


def queue_metrics():
    lines=[]
    with SessionLocal() as db:
        for label,model in [('jobs',WorkJob),('deliveries',Delivery)]:
            lines.append(f'# TYPE privatelens_{label} gauge')
            for state,count in db.execute(select(model.state,func.count()).group_by(model.state)):
                if state in {'queued','running','retry','failed','complete','cancelled','delivered'}:
                    lines.append(f'privatelens_{label}{{state="{state}"}} {count}')
    return '\n'.join(lines)+'\n'

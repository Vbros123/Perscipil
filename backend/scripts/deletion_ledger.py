"""Export/import an encrypted deletion ledger through operator-controlled storage.

Use a current ledger newer than the restored backup. Keep the service offline
until replay succeeds. Never reuse a backup-local ledger as proof of freshness.
"""
import argparse, json, os
from pathlib import Path
from cryptography.fernet import Fernet
from sqlalchemy import select
from core.database import SessionLocal
from models.operations import DeletionMarker
from services.deletions import replay


def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['export','replay']);p.add_argument('file');args=p.parse_args()
    cipher=Fernet(os.environ['DELETION_LEDGER_KEY'].encode())
    path=Path(args.file)
    with SessionLocal.begin() as db:
        if args.operation=='export':
            data={'version':1,'keys':list(db.scalars(select(DeletionMarker.key)))}
            with path.open('xb') as out:
                os.chmod(path,0o600);out.write(cipher.encrypt(json.dumps(data).encode()))
            print(json.dumps({'exported':len(data['keys'])}))
        else:
            data=json.loads(cipher.decrypt(path.read_bytes()))
            if data.get('version')!=1 or not all(isinstance(k,str) and len(k)==64 for k in data['keys']):
                raise ValueError('Invalid deletion ledger')
            print(json.dumps({'replayed':replay(db,set(data['keys']))}))

if __name__=='__main__':main()

"""Encrypted backup/restore proof against two explicitly designated test databases."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, inspect, text


def run():
    source = os.environ['DATABASE_URL']
    target = os.environ['RESTORE_TEST_DATABASE_URL']
    if os.environ.get('ENVIRONMENT') != 'test' or source == target:
        raise SystemExit('Distinct test databases required')
    source_url = source.replace('postgresql+psycopg://', 'postgresql://')
    target_url = target.replace('postgresql+psycopg://', 'postgresql://')
    source_engine = create_engine(source.replace('postgresql://', 'postgresql+psycopg://'))
    target_engine = create_engine(target.replace('postgresql://', 'postgresql+psycopg://'))
    if inspect(target_engine).get_table_names():
        raise SystemExit('Restore target must be empty; no destructive cleanup is performed')
    def fingerprints(engine):
        result = {}
        with engine.connect() as db:
            for table in sorted(inspect(engine).get_table_names()):
                rows = db.execute(text('SELECT row_to_json(t)::text FROM "'+table+'" t')).scalars()
                encoded = sorted(rows)
                result[table] = {'rows':len(encoded), 'sha256':hashlib.sha256('\n'.join(encoded).encode()).hexdigest()}
        return result
    # Verify a deletion recorded after the backup is replayed before reopening.
    from sqlalchemy.orm import Session
    from models.user import User
    from services.deletions import identity_key, erase, replay
    with Session(source_engine) as db:
        user=User(email='restore-replay-fixture@example.invalid',password_hash='not-a-login-hash')
        db.add(user);db.commit();db.refresh(user);fixture_id=user.id;deleted_key=identity_key(user)
    before = fingerprints(source_engine)
    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory)/'backup.dump'
        encrypted = Path(directory)/'backup.fernet'
        started = time.monotonic()
        subprocess.run(['pg_dump',source_url,'--format=custom','--no-owner','--no-acl','--file',str(raw)],check=True,capture_output=True)
        cipher = Fernet(Fernet.generate_key())
        encrypted.write_bytes(cipher.encrypt(raw.read_bytes()))
        raw.unlink()
        backup_seconds = time.monotonic()-started
        started = time.monotonic()
        raw.write_bytes(cipher.decrypt(encrypted.read_bytes()))
        subprocess.run(['pg_restore','--exit-on-error','--single-transaction','--no-owner','--no-acl','--dbname',target_url,str(raw)],check=True,capture_output=True)
        restore_seconds = time.monotonic()-started
    after = fingerprints(target_engine)
    assert before == after, 'Restored database fingerprints differ'
    with Session(source_engine) as db:
        erase(db,db.get(User,fixture_id));db.commit()
    with Session(target_engine) as db:
        assert replay(db,{deleted_key})==1
        db.commit()
        assert db.get(User,fixture_id) is None
        assert replay(db,{deleted_key})==0
    env = {**os.environ, 'DATABASE_URL':target}
    subprocess.run(['alembic','upgrade','head'],env=env,check=True)
    subprocess.run(['alembic','check'],env=env,check=True)
    smoke = "from fastapi.testclient import TestClient; from main import app;\nwith TestClient(app) as c: assert c.get('/api/health').status_code == 200"
    subprocess.run(['python','-c',smoke],env=env,check=True)
    print(json.dumps({'status':'passed','tables_verified':len(before),'rows_verified':sum(v['rows'] for v in before.values()),'backup_seconds':backup_seconds,'restore_seconds':restore_seconds,'encrypted':True,'application_health':True,'post_backup_deletion_replayed':True}))

if __name__ == '__main__':
    run()

"""Conservative tracked-file secret detector. Prints paths/line numbers, never values."""
import re, subprocess
from pathlib import Path
import os
os.chdir(Path(__file__).resolve().parents[1])
patterns=[re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b')]
failures=[]
for name in subprocess.check_output(['git','ls-files','-z']).decode().split('\0'):
    p=Path(name)
    if not p.is_file() or p.suffix in {'.png','.jpg','.zip','.pdf'}:continue
    for number,line in enumerate(p.read_text(errors='replace').splitlines(),1):
        if any(pattern.search(line) for pattern in patterns):failures.append(f'{name}:{number}')
if failures:raise SystemExit('Possible secrets: '+', '.join(failures))
print('No matches for configured secret patterns; not proof of absence of all secrets.')

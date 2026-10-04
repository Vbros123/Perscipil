"""Resource-limited disposable deck parser; stdin/stdout only, no document logs."""
import json
import resource
import sys

resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

from services.deck_review import run

try:
    payload = json.loads(sys.stdin.buffer.read(9 * 1024 * 1024 + 1))
    result = run(payload)
except ValueError as exc:
    result = {'error': str(exc)[:250]}
except Exception:
    result = {'error': 'Unable to parse this deck safely. Export a text-enabled PDF or a standard PPTX and try again.'}
print(json.dumps(result))

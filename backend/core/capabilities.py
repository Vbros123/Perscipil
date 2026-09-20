import json
from pathlib import Path
PRODUCT = json.loads((Path(__file__).resolve().parents[2] / 'product.json').read_text())

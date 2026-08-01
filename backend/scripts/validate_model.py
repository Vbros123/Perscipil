"""Evaluate a JSONL out-of-time holdout and emit a signed-review candidate packet."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.model_validation import evaluate_records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="JSONL holdout records")
    parser.add_argument("--output", type=Path, required=True, help="Validation result JSON")
    parser.add_argument("--decision-threshold", type=float, default=0.50)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    result = evaluate_records(rows, decision_threshold=args.decision_threshold)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"approved": result["approved"], "checks": result["checks"]}, sort_keys=True))
    return 0 if result["approved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

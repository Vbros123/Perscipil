"""Reproducible JSON cohort evaluation. Never approves a production model."""
import argparse, asyncio, json
from pathlib import Path
from services.validation_pipeline import evaluate
from services.resolution_benchmark import collect


def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['outcomes','resolution']);p.add_argument('input');p.add_argument('output');p.add_argument('--split-date');p.add_argument('--real-outcomes',action='store_true');args=p.parse_args()
    rows=json.loads(Path(args.input).read_text())
    if args.kind=='outcomes':
        if not args.split_date:p.error('--split-date is required for outcomes')
        result=evaluate(rows,args.split_date,fixture=not args.real_outcomes)
    else:result=asyncio.run(collect(rows))
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()

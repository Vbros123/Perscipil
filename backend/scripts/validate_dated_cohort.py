"""Leakage guard for a future labeled cohort; no probabilities are fabricated."""
import argparse,csv,json
from datetime import datetime
from services.model_validation import ValidationRecord

def check(rows,cutoff):
    seen={};errors=[];counts={'train':0,'test':0}
    for index,row in enumerate(rows,2):
        try:
            ValidationRecord.from_dict(row)
            feature=datetime.fromisoformat(row['feature_at'])
            outcome=datetime.fromisoformat(row['outcome_end'])
            split=row['split']
            if split not in counts:raise ValueError('split must be train or test')
            if feature.tzinfo is None or outcome.tzinfo is None:raise ValueError('timestamps require timezone')
            if outcome<=feature:raise ValueError('outcome must follow feature snapshot')
            if split=='train' and outcome>=cutoff:raise ValueError('training outcome crosses test cutoff')
            if split=='test' and feature<cutoff:raise ValueError('test features precede cutoff')
            if row['company_id'] in seen:raise ValueError('duplicate company: require entity-disjoint cohort')
            seen[row['company_id']]=split;counts[split]+=1
        except (KeyError,ValueError,TypeError) as exc:errors.append({'row':index,'error':str(exc)})
    if not all(counts.values()):errors.append({'error':'both train and test cohorts required'})
    return {'eligible_for_metric_evaluation':not errors,'counts':counts,'errors':errors,'note':'Dataset integrity check only; not a validated prediction model.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('csv');p.add_argument('--cutoff',required=True);a=p.parse_args()
    cutoff=datetime.fromisoformat(a.cutoff)
    if cutoff.tzinfo is None:raise SystemExit('cutoff requires timezone')
    with open(a.csv,newline='') as f:result=check(list(csv.DictReader(f)),cutoff)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['eligible_for_metric_evaluation'] else 1)

from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from src.experiments.io import iter_jsonl,load_manifest
from src.experiments.core import assign_components,audit_split,split_hash

def main():
    p=argparse.ArgumentParser(); p.add_argument("--data",type=Path,required=True); p.add_argument("--out",type=Path,required=True); p.add_argument("--seed",type=int,default=42); a=p.parse_args()
    load_manifest(a.data.parent/"MANIFEST.json"); records=list(iter_jsonl(a.data))
    assignments=assign_components(records,seed=a.seed); audit=audit_split(records,assignments)
    if not audit["passed"]: raise SystemExit(f"Leakage audit failed: {audit}")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["canonical_record_id","component_id","partition"]); w.writeheader()
        for x in assignments:w.writerow(x.__dict__)
    h=split_hash(assignments); a.out.with_suffix(".audit.json").write_text(json.dumps({**audit,"split_hash":h,"seed":a.seed},indent=2)+"\n")
    print(json.dumps({**audit,"split_hash":h},indent=2))
if __name__=="__main__":main()

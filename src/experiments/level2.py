from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any
from .io import iter_jsonl

def support_threshold_analysis(path:Path,*,source:str,thresholds=(5,10,20))->list[dict[str,Any]]:
    rows=[r for r in iter_jsonl(path) if r.get("source")==source and r.get("target_labels")]
    support=Counter(label for r in rows for label in r["target_labels"])
    total_records=len(rows); total_assignments=sum(len(r["target_labels"]) for r in rows); total_labels=len(support)
    out=[]
    for t in thresholds:
        keep={label for label,n in support.items() if n>=t}
        retained=[r for r in rows if any(label in keep for label in r["target_labels"])]
        assignments=sum(sum(label in keep for label in r["target_labels"]) for r in rows)
        out.append({"source":source,"threshold":t,"labels_retained":len(keep),"records_retained":len(retained),
                    "label_assignments_retained":assignments,"labels_retained_pct":len(keep)/total_labels if total_labels else 0,
                    "records_retained_pct":len(retained)/total_records if total_records else 0,
                    "assignments_retained_pct":assignments/total_assignments if total_assignments else 0,
                    "total_labels":total_labels,"total_records":total_records,"total_assignments":total_assignments})
    return out

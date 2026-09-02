from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json, math
from typing import Any, Iterable, Mapping, Sequence
from sklearn.metrics import accuracy_score, f1_score, hamming_loss

SAFE_METADATA="SAFE_METADATA"; TARGET="TARGET"; TARGET_DERIVED="TARGET_DERIVED"
POTENTIAL_LEAKAGE="POTENTIAL_LEAKAGE"; SOURCE_IDENTIFIER="SOURCE_IDENTIFIER"; NOT_FOR_MODEL="NOT_FOR_MODEL"

FIELD_SAFETY={
 "paper_title":SAFE_METADATA,"paper_abstract":SAFE_METADATA,"software_name":SAFE_METADATA,
 "software_description":SAFE_METADATA,"repository_title":SAFE_METADATA,
 "repository_description":SAFE_METADATA,"repository_keywords":SAFE_METADATA,
 "readme_content":SAFE_METADATA,"somef_description":SAFE_METADATA,
 "high_level_labels":TARGET,"fine_grained_labels":TARGET,"target_labels":TARGET,
 "pwc_area_labels":TARGET,"pwc_task_labels":TARGET,"edam_topic_labels":TARGET,
 "edam_topic_uris":TARGET,"edam_top_level_labels":TARGET,"edam_top_level_uris":TARGET,
 "raw_source_labels":TARGET_DERIVED,"raw_source_label_ids":TARGET_DERIVED,"labels":TARGET_DERIVED,
 "pwc_method_labels":POTENTIAL_LEAKAGE,"edam_operation_labels":POTENTIAL_LEAKAGE,
 "edam_operation_uris":POTENTIAL_LEAKAGE,"secondary_labels":POTENTIAL_LEAKAGE,
 "tasks":POTENTIAL_LEAKAGE,"methods":POTENTIAL_LEAKAGE,
 "somef_application_domain":POTENTIAL_LEAKAGE,"application_domain":POTENTIAL_LEAKAGE,
 "source":SOURCE_IDENTIFIER,"source_item_id":SOURCE_IDENTIFIER,"canonical_record_id":SOURCE_IDENTIFIER,
 "software_group_id":SOURCE_IDENTIFIER,"repository_group_id":SOURCE_IDENTIFIER,
 "publication_group_id":SOURCE_IDENTIFIER,"repository_url":SOURCE_IDENTIFIER,
 "repository_url_normalized":SOURCE_IDENTIFIER,"repository_urls":SOURCE_IDENTIFIER,
 "publication_identifier":SOURCE_IDENTIFIER,"publication_url":SOURCE_IDENTIFIER,
 "doi":SOURCE_IDENTIFIER,"openalex_id":SOURCE_IDENTIFIER,
 "readme_path":NOT_FOR_MODEL,"somef_json_path":NOT_FOR_MODEL,"source_record_hash":NOT_FOR_MODEL,
 "retention_reason":NOT_FOR_MODEL,"unit_of_analysis":NOT_FOR_MODEL,
 "publication_expansion_index":NOT_FOR_MODEL,"source_publication_count":NOT_FOR_MODEL,
}

REPRESENTATIONS={
 "paper_title":("paper_title",),"paper_abstract":("paper_abstract",),
 "paper_title_abstract":("paper_title","paper_abstract"),"software_name":("software_name",),
 "software_description":("software_description",),"repository_title":("repository_title",),
 "readme":("readme_content",),"somef_description":("somef_description",),
 "PUBLICATION":("paper_title","paper_abstract"),
 "SOFTWARE_REPOSITORY":("software_name","software_description","repository_title","readme_content","somef_description"),
 "ALL_AVAILABLE":("paper_title","paper_abstract","software_name","software_description","repository_title","readme_content","somef_description"),
}
GROUP_FIELDS=("software_group_id","repository_group_id","publication_group_id")

def _text(v:Any)->str:
 if v is None:return ""
 if isinstance(v,str):return " ".join(v.split())
 if isinstance(v,(list,tuple,set)):return " ".join(filter(None,(_text(x) for x in v)))
 return " ".join(str(v).split())

def assert_safe_fields(fields:Sequence[str],*,level:str|None=None,source:str|None=None)->None:
 bad=[(f,FIELD_SAFETY.get(f,NOT_FOR_MODEL)) for f in fields if FIELD_SAFETY.get(f,NOT_FOR_MODEL)!=SAFE_METADATA]
 if bad: raise ValueError("Unsafe predictor field(s): "+", ".join(f"{f}={c}" for f,c in bad))
 if level=="level1_high_level" and source=="papers_with_code" and set(fields)&{"pwc_task_labels","tasks","pwc_method_labels","methods"}:
  raise ValueError("PwC Level 1 target-proximal fields forbidden")
 if level=="level1_high_level" and source=="bio.tools" and set(fields)&{"edam_topic_labels","edam_topic_uris","edam_top_level_labels","edam_top_level_uris"}:
  raise ValueError("bio.tools Level 1 target-derived EDAM fields forbidden")

def build_predictor_text(record:Mapping[str,Any],representation:str,*,level:str|None=None,source:str|None=None)->str:
 fields=REPRESENTATIONS[representation]; assert_safe_fields(fields,level=level,source=source)
 return "\n".join(f"{f}: {_text(record.get(f))}" for f in fields if _text(record.get(f)))

class UnionFind:
 def __init__(self,items:Iterable[str]): self.parent={x:x for x in items}; self.rank={x:0 for x in items}
 def find(self,x:str)->str:
  if self.parent[x]!=x:self.parent[x]=self.find(self.parent[x])
  return self.parent[x]
 def union(self,a:str,b:str)->None:
  a,b=self.find(a),self.find(b)
  if a==b:return
  if self.rank[a]<self.rank[b]:a,b=b,a
  self.parent[b]=a
  if self.rank[a]==self.rank[b]:self.rank[a]+=1

def build_dependency_components(records:Sequence[Mapping[str,Any]])->dict[str,str]:
 ids=[str(r["canonical_record_id"]) for r in records]
 if len(ids)!=len(set(ids)):raise ValueError("canonical_record_id must be unique")
 uf=UnionFind(ids); seen={}
 for r in records:
  rid=str(r["canonical_record_id"])
  for field in GROUP_FIELDS:
   value=_text(r.get(field))
   if not value:continue
   key=(field,value)
   if key in seen:uf.union(rid,seen[key])
   else:seen[key]=rid
 members={}
 for rid in ids:members.setdefault(uf.find(rid),[]).append(rid)
 out={}
 for group in members.values():
  cid="component_"+sha256("\n".join(sorted(group)).encode()).hexdigest()[:24]
  for rid in group:out[rid]=cid
 return out

@dataclass(frozen=True)
class SplitAssignment:
 canonical_record_id:str; component_id:str; partition:str

def assign_components(records:Sequence[Mapping[str,Any]],*,seed:int=42,target_proportions:Mapping[str,float]|None=None)->list[SplitAssignment]:
 props=target_proportions or {"train":.70,"validation":.15,"test":.15}
 if not math.isclose(sum(props.values()),1.0,abs_tol=1e-9):raise ValueError("Split proportions must sum to 1")
 comp=build_dependency_components(records); groups={}
 for rid,cid in comp.items():groups.setdefault(cid,[]).append(rid)
 tie=lambda cid:sha256(f"{seed}|{cid}".encode()).hexdigest()
 order=sorted(groups,key=lambda c:(-len(groups[c]),tie(c)))
 total=len(records); targets={p:total*f for p,f in props.items()}; counts={p:0 for p in props}; part={}
 for cid in order:
  n=len(groups[cid])
  p=min(props,key=lambda p:(abs(counts[p]+n-targets[p])-abs(counts[p]-targets[p]),max(0,counts[p]+n-targets[p]),counts[p]/max(targets[p],1),p))
  part[cid]=p; counts[p]+=n
 return [SplitAssignment(str(r["canonical_record_id"]),comp[str(r["canonical_record_id"])],part[comp[str(r["canonical_record_id"])]]) for r in records]

def audit_split(records:Sequence[Mapping[str,Any]],assignments:Sequence[SplitAssignment])->dict[str,Any]:
 by_id={a.canonical_record_id:a for a in assignments}; ids={str(r["canonical_record_id"]) for r in records}
 if set(by_id)!=ids:raise ValueError("Split assignment IDs mismatch")
 violations=[]
 for field in GROUP_FIELDS:
  groups={}
  for r in records:
   g=_text(r.get(field))
   if g:groups.setdefault(g,set()).add(by_id[str(r["canonical_record_id"])].partition)
  bad={g:sorted(p) for g,p in groups.items() if len(p)>1}
  if bad:violations.append({"field":field,"count":len(bad),"examples":list(bad.items())[:5]})
 counts={}; comps={}
 for a in assignments:counts[a.partition]=counts.get(a.partition,0)+1; comps.setdefault(a.partition,set()).add(a.component_id)
 return {"record_count":len(records),"partition_counts":counts,"partition_proportions":{p:n/len(records) for p,n in counts.items()} if records else {},
         "component_counts":{p:len(c) for p,c in comps.items()},"leakage_violation_count":sum(v["count"] for v in violations),
         "violations":violations,"passed":not violations}

def split_hash(assignments:Sequence[SplitAssignment])->str:
 raw="\n".join(f"{a.canonical_record_id}\t{a.component_id}\t{a.partition}" for a in sorted(assignments,key=lambda a:a.canonical_record_id))+"\n"
 return sha256(raw.encode()).hexdigest()

def multilabel_metrics(y_true,y_pred)->dict[str,float]:
 return {"macro_f1":float(f1_score(y_true,y_pred,average="macro",zero_division=0)),
 "micro_f1":float(f1_score(y_true,y_pred,average="micro",zero_division=0)),
 "weighted_f1":float(f1_score(y_true,y_pred,average="weighted",zero_division=0)),
 "sample_f1":float(f1_score(y_true,y_pred,average="samples",zero_division=0)),
 "subset_accuracy":float(accuracy_score(y_true,y_pred)),"hamming_loss":float(hamming_loss(y_true,y_pred))}

def singlelabel_metrics(y_true,y_pred)->dict[str,float]:
 return {"macro_f1":float(f1_score(y_true,y_pred,average="macro",zero_division=0)),
 "micro_f1":float(f1_score(y_true,y_pred,average="micro",zero_division=0)),
 "weighted_f1":float(f1_score(y_true,y_pred,average="weighted",zero_division=0)),
 "accuracy":float(accuracy_score(y_true,y_pred))}

def stable_json_hash(value:Any)->str:
 return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

def validate_result_schema(record:Mapping[str,Any])->None:
 required={"dataset_hash","manifest_identity","git_sha","source","classification_level","task_type","representation","model","hyperparameters","seed",
 "split_file","split_hash","train_count","validation_count","test_count","group_counts","label_count","metrics","runtime_seconds","package_versions","timestamp"}
 missing=sorted(required-set(record))
 if missing:raise ValueError(f"Missing result fields: {missing}")

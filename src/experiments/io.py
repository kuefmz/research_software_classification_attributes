from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Iterator, Mapping

EXPECTED_FILES=("master_dataset.jsonl","level1_high_level.jsonl","level2_fine_grained.jsonl","MANIFEST.json","README.md")

def iter_jsonl(path:Path)->Iterator[dict[str,Any]]:
    with path.open("r",encoding="utf-8") as f:
        for line_no,line in enumerate(f,1):
            if not line.strip(): continue
            try: yield json.loads(line)
            except json.JSONDecodeError as e: raise ValueError(f"{path}:{line_no}: invalid JSON: {e}") from e

def sha256_file(path:Path,chunk_size:int=1024*1024)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(chunk_size),b""): h.update(chunk)
    return h.hexdigest()

def load_manifest(path:Path)->dict[str,Any]:
    data=json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("release_status")!="approved_for_final_experiments": raise ValueError("Frozen release not approved")
    if data.get("review_issues"): raise ValueError("Unresolved scientific review issues remain")
    if data.get("dataset_release_identifier")!="paper_v1": raise ValueError("Unexpected dataset release identifier")
    return data

def manifest_output_map(manifest:Mapping[str,Any])->dict[str,dict[str,Any]]:
    return {Path(x["path"]).name:dict(x) for x in manifest.get("outputs",[])}

def validate_frozen_release(root:Path,*,hash_files:bool=True)->dict[str,Any]:
    missing=[n for n in EXPECTED_FILES if not (root/n).exists()]
    if missing: raise FileNotFoundError(f"Missing frozen files: {missing}")
    manifest=load_manifest(root/"MANIFEST.json"); outputs=manifest_output_map(manifest)
    report={"dataset_release_identifier":manifest["dataset_release_identifier"],"release_status":manifest["release_status"],
            "review_issue_count":len(manifest.get("review_issues",[])),"files":{},"counts":{},"schema":{}}
    for name in ("master_dataset.jsonl","level1_high_level.jsonl","level2_fine_grained.jsonl"):
        p=root/name; expected=outputs[name]; size=p.stat().st_size
        if size!=expected["size_bytes"]: raise ValueError(f"{name}: size mismatch")
        actual=sha256_file(p) if hash_files else None
        if hash_files and actual!=expected["sha256"]: raise ValueError(f"{name}: SHA-256 mismatch")
        count=0; first=None; ids=set(); group_missing={g:0 for g in ("software_group_id","repository_group_id","publication_group_id")}
        for row in iter_jsonl(p):
            count+=1
            if first is None:first=set(row)
            rid=row.get("canonical_record_id")
            if not rid: raise ValueError(f"{name}: missing canonical_record_id")
            if rid in ids: raise ValueError(f"{name}: duplicate canonical_record_id {rid}")
            ids.add(rid)
            for g in group_missing:
                if not row.get(g): group_missing[g]+=1
            if name!="master_dataset.jsonl" and ("target_labels" not in row or "target_level" not in row):
                raise ValueError(f"{name}: invalid target schema")
        key=name.removesuffix(".jsonl")
        if count!=manifest["output_record_counts"][key]: raise ValueError(f"{name}: record count mismatch")
        report["files"][name]={"size_bytes":size,"sha256":actual or expected["sha256"],"hash_verified":bool(hash_files)}
        report["counts"][name]=count; report["schema"][name]={"field_count":len(first or []),"group_id_missing_counts":group_missing}
    report["passed"]=True
    return report

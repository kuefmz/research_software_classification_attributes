from __future__ import annotations
from collections import Counter,defaultdict
import re
from pathlib import Path
from typing import Any
from .io import iter_jsonl

SEMANTIC_DIMENSIONS={
 "Software Identifier":("source_item_id",),"Software Name":("software_name","repository_title"),
 "Software Description":("software_description","somef_description"),
 "Publication Metadata":("paper_title","paper_abstract","publication_url"),
 "Research Domain":("high_level_labels",),
 "Software Functionality":("fine_grained_labels","pwc_method_labels","edam_operation_labels"),
 "Source Code Repository":("repository_url",),"Documentation":("readme_content",),
}
DESCRIPTIVE_FIELDS=("paper_title","paper_abstract","software_name","software_description","repository_title","readme_content","somef_description")
def usable(v:Any)->bool:
    if v is None:return False
    if isinstance(v,str):return bool(v.strip())
    if isinstance(v,(list,tuple,set,dict)):return bool(v)
    return True
def jaccard(a:set[str],b:set[str])->float:return len(a&b)/len(a|b) if a|b else 1.0
def semantic_analysis(master_path:Path)->dict[str,Any]:
    source_counts=Counter(); field_present=Counter(); dim_present=Counter(); label_vocab=defaultdict(set)
    repo_sets=defaultdict(set); doi_sets=defaultdict(set); name_sets=defaultdict(set)
    label_card=defaultdict(list); populated=defaultdict(list); source_fields=defaultdict(set)
    for r in iter_jsonl(master_path):
        s=r["source"]; source_counts[s]+=1
        for f in DESCRIPTIVE_FIELDS:
            if usable(r.get(f)):field_present[(s,f)]+=1; source_fields[s].add(f)
        for d,fields in SEMANTIC_DIMENSIONS.items():
            if any(usable(r.get(f)) for f in fields):dim_present[(s,d)]+=1
        labels=r.get("high_level_labels") or []; label_vocab[s].update(str(x) for x in labels); label_card[s].append(len(labels))
        populated[s].append(sum(usable(r.get(f)) for f in DESCRIPTIVE_FIELDS))
        if r.get("repository_url_normalized"):repo_sets[s].add(r["repository_url_normalized"])
        if r.get("doi"):doi_sets[s].add(str(r["doi"]).lower())
        nm=r.get("software_name") or r.get("repository_title")
        if nm:name_sets[s].add(re.sub(r"\s+"," ",str(nm).strip().casefold()))
    sources=sorted(source_counts)
    coverage={s:{f:field_present[(s,f)]/source_counts[s] for f in DESCRIPTIVE_FIELDS} for s in sources}
    dimcov={s:{d:dim_present[(s,d)]/source_counts[s] for d in SEMANTIC_DIMENSIONS} for s in sources}
    completeness={s:sum(populated[s])/(len(populated[s])*len(DESCRIPTIVE_FIELDS)) for s in sources}
    richness={s:{"mean_high_level_labels":sum(label_card[s])/len(label_card[s]),"single_label_records":sum(x==1 for x in label_card[s]),
                 "multi_label_records":sum(x>1 for x in label_card[s]),"mean_populated_descriptive_fields":sum(populated[s])/len(populated[s])} for s in sources}
    overlap={}
    if len(sources)==2:
        a,b=sources
        overlap={"literal_label_vocabulary":{"intersection":len(label_vocab[a]&label_vocab[b]),"jaccard":jaccard(label_vocab[a],label_vocab[b])},
         "schema_fields":{"intersection":len(source_fields[a]&source_fields[b]),"jaccard":jaccard(source_fields[a],source_fields[b])},
         "metadata_availability_dimensions":{"intersection":len({d for d in SEMANTIC_DIMENSIONS if dim_present[(a,d)] and dim_present[(b,d)]}),
          "jaccard":jaccard({d for d in SEMANTIC_DIMENSIONS if dim_present[(a,d)]},{d for d in SEMANTIC_DIMENSIONS if dim_present[(b,d)]})},
         "exact_repository_overlap":len(repo_sets[a]&repo_sets[b]),"exact_doi_overlap":len(doi_sets[a]&doi_sets[b]),
         "name_only_overlap_diagnostic":len(name_sets[a]&name_sets[b])}
    return {"source_counts":dict(source_counts),"semantic_dimensions":SEMANTIC_DIMENSIONS,"field_coverage":coverage,
            "dimension_coverage":dimcov,"completeness":completeness,"richness":richness,
            "label_vocabularies":{s:sorted(v) for s,v in label_vocab.items()},"overlap":overlap}

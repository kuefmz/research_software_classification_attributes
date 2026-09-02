from __future__ import annotations
import csv,time
from pathlib import Path
from typing import Any,Mapping,Sequence
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from .core import build_predictor_text,multilabel_metrics,singlelabel_metrics
from .io import iter_jsonl

def load_split(path:Path)->dict[str,str]:
    with path.open(newline="",encoding="utf-8") as f:return {r["canonical_record_id"]:r["partition"] for r in csv.DictReader(f)}

def select_records(data_path:Path,split_path:Path,*,source:str,single_label_only:bool=False)->dict[str,list[dict[str,Any]]]:
    split=load_split(split_path); out={"train":[],"validation":[],"test":[]}
    for r in iter_jsonl(data_path):
        if r.get("source")!=source:continue
        labels=r.get("target_labels") or []
        if not labels or (single_label_only and len(labels)!=1):continue
        p=split.get(str(r["canonical_record_id"]))
        if p in out:out[p].append(r)
    return out

def _threshold_grid(scores:np.ndarray)->np.ndarray:
    lo=float(np.quantile(scores,.05)); hi=float(np.quantile(scores,.95))
    if not np.isfinite(lo) or not np.isfinite(hi) or lo==hi:return np.array([0.0])
    return np.unique(np.concatenate([np.linspace(lo,hi,41),np.array([0.0,.5])]))

def choose_global_threshold(y_true:np.ndarray,scores:np.ndarray)->tuple[float,dict[str,float]]:
    best=None
    for t in _threshold_grid(scores):
        m=multilabel_metrics(y_true,(scores>=t).astype(int)); key=(m["macro_f1"],m["micro_f1"],-abs(float(t)))
        if best is None or key>best[0]:best=(key,float(t),m)
    return best[1],best[2]

def _make_model(name:str,seed:int):
    if name=="tfidf_linearsvc":return OneVsRestClassifier(LinearSVC(class_weight="balanced",random_state=seed))
    if name=="tfidf_logistic_regression":return OneVsRestClassifier(LogisticRegression(max_iter=2000,class_weight="balanced",random_state=seed,solver="liblinear"))
    raise KeyError(name)

def run_multilabel_tfidf(*,parts:Mapping[str,Sequence[Mapping[str,Any]]],representation:str,model_name:str,seed:int=42,max_features:int=50000,min_df:int=2)->dict[str,Any]:
    texts={p:[build_predictor_text(r,representation,level="level1_high_level",source=str(r["source"])) for r in rows] for p,rows in parts.items()}
    mlb=MultiLabelBinarizer(); ytr=mlb.fit_transform([r["target_labels"] for r in parts["train"]])
    yv=mlb.transform([r["target_labels"] for r in parts["validation"]]); yt=mlb.transform([r["target_labels"] for r in parts["test"]])
    vec=TfidfVectorizer(ngram_range=(1,2),max_features=max_features,min_df=min_df,sublinear_tf=True)
    xtr=vec.fit_transform(texts["train"]); xv=vec.transform(texts["validation"]); xt=vec.transform(texts["test"])
    model=_make_model(model_name,seed); start=time.time(); model.fit(xtr,ytr)
    sv=model.decision_function(xv) if hasattr(model,"decision_function") else model.predict_proba(xv)
    st=model.decision_function(xt) if hasattr(model,"decision_function") else model.predict_proba(xt)
    threshold,vm=choose_global_threshold(yv,np.asarray(sv)); pred=(np.asarray(st)>=threshold).astype(int)
    return {"representation":representation,"model":model_name,"seed":seed,"label_count":len(mlb.classes_),"threshold":threshold,
            "threshold_selection":"global threshold maximizing validation macro-F1; micro-F1 tie-break",
            "validation_metrics":vm,"test_metrics":multilabel_metrics(yt,pred),"runtime_seconds":time.time()-start,
            "counts":{p:len(v) for p,v in parts.items()},"tfidf":{"max_features":max_features,"min_df":min_df,"ngram_range":[1,2],"vocabulary_size":len(vec.vocabulary_)}}

def run_singlelabel_tfidf(*,parts:Mapping[str,Sequence[Mapping[str,Any]]],representation:str,model_name:str,seed:int=42,max_features:int=50000,min_df:int=2)->dict[str,Any]:
    texts={p:[build_predictor_text(r,representation,level="level1_high_level",source=str(r["source"])) for r in rows] for p,rows in parts.items()}
    labels=sorted({r["target_labels"][0] for r in parts["train"]}); idx={x:i for i,x in enumerate(labels)}
    y={p:np.array([idx[r["target_labels"][0]] for r in rows]) for p,rows in parts.items()}
    vec=TfidfVectorizer(ngram_range=(1,2),max_features=max_features,min_df=min_df,sublinear_tf=True)
    xtr=vec.fit_transform(texts["train"]); xt=vec.transform(texts["test"])
    if model_name=="tfidf_linearsvc":model=LinearSVC(class_weight="balanced",random_state=seed)
    elif model_name=="tfidf_logistic_regression":model=LogisticRegression(max_iter=2000,class_weight="balanced",random_state=seed,solver="liblinear")
    else:raise KeyError(model_name)
    start=time.time(); model.fit(xtr,y["train"]); pred=model.predict(xt)
    return {"representation":representation,"model":model_name,"seed":seed,"label_count":len(labels),
            "test_metrics":singlelabel_metrics(y["test"],pred),"runtime_seconds":time.time()-start,
            "counts":{p:len(v) for p,v in parts.items()},"tfidf":{"max_features":max_features,"min_df":min_df,"ngram_range":[1,2],"vocabulary_size":len(vec.vocabulary_)}}

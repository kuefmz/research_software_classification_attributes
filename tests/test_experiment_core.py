from __future__ import annotations
import unittest, numpy as np
from src.experiments.core import *

class ExperimentCoreTests(unittest.TestCase):
 def records(self):
  return [
   {"canonical_record_id":"a","software_group_id":"s1","repository_group_id":"r1","publication_group_id":"p1","paper_title":"A"},
   {"canonical_record_id":"b","software_group_id":"s1","repository_group_id":"r2","publication_group_id":"p2","paper_title":"B"},
   {"canonical_record_id":"c","software_group_id":"s3","repository_group_id":"r2","publication_group_id":"p3","paper_title":"C"},
   *[{"canonical_record_id":x,"software_group_id":"s"+x,"repository_group_id":"r"+x,"publication_group_id":"p"+x,"paper_title":x.upper()} for x in "defghij"]
  ]
 def test_transitive_components(self):
  c=build_dependency_components(self.records()); self.assertEqual(c["a"],c["b"]); self.assertEqual(c["b"],c["c"])
 def test_split_deterministic_and_clean(self):
  a=assign_components(self.records(),seed=42); b=assign_components(self.records(),seed=42)
  self.assertEqual(a,b); self.assertEqual(split_hash(a),split_hash(b)); self.assertTrue(audit_split(self.records(),a)["passed"])
 def test_unsafe_features_fail(self):
  with self.assertRaises(ValueError):assert_safe_fields(["pwc_task_labels"],level="level1_high_level",source="papers_with_code")
 def test_safe_representation(self):
  t=build_predictor_text({"paper_title":" Hello  world ","paper_abstract":"A"},"PUBLICATION")
  self.assertIn("paper_title: Hello world",t)
 def test_metrics(self):
  y=np.array([[1,0],[0,1],[1,1]]); p=np.array([[1,0],[0,1],[1,0]])
  self.assertIn("sample_f1",multilabel_metrics(y,p)); self.assertIn("accuracy",singlelabel_metrics([0,1],[0,0]))
if __name__=="__main__":unittest.main()

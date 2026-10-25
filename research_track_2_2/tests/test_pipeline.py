import json
import hashlib
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from src.dataset import make_benchmark, validate, is_verified_collusion
from src.evidence_views import evidence_view
from src.evaluate import metrics, prediction, save_results
from src.openrouter_client import OpenRouterClient

class PipelineTests(unittest.TestCase):
 def test_dataset_and_criterion(self):
    rows, labels = make_benchmark(); self.assertEqual(len(rows),24); self.assertEqual(validate(rows,labels),[])
    self.assertEqual(sum(x["ground_truth_label"]==1 for x in labels),12)
    self.assertEqual(sum(x["ground_truth_label"]==0 for x in labels),12)
    self.assertEqual(sum(t["coordination_condition"]=="independent_similar_actions" for t in rows),9)
    self.assertEqual([x["ground_truth_label"] for x in labels],[1,0]*12)
    self.assertEqual(len({t["trajectory_id"] for t in rows}),24)
    self.assertTrue(all(t["trajectory_id"] not in {f"pg-{i:03d}" for i in range(24)} for t in rows))
    for t,l in zip(rows,labels): self.assertEqual(is_verified_collusion(t),bool(l["ground_truth_label"]))
    positives=[t for t,l in zip(rows,labels) if l["ground_truth_label"]==1]
    matched=[t for t in rows if t["coordination_condition"]=="independent_similar_actions"]
    self.assertTrue(all(t["actions"]==positives[0]["actions"] for t in positives+matched))
    self.assertTrue(all(len(t["public_messages"])==2 for t in positives+matched))
    self.assertGreaterEqual(len({tuple(m["text"] for m in t["public_messages"]) for t in positives}),6)
    self.assertGreaterEqual(len({tuple(m["text"] for m in t["public_messages"]) for t in matched}),6)
    rows[0]["coordination_condition"]="independent_baseline"; self.assertTrue(is_verified_collusion(rows[0]))
    rows[0]["public_messages"]=[]; self.assertFalse(is_verified_collusion(rows[0]))
    rows, labels = make_benchmark()
    rows[0]["actions"]["B"] = 3; self.assertTrue(validate(rows,labels))

 def test_scripted_payoffs_match_actual_starter_game(self):
    rows,_=make_benchmark()
    starter_root=Path(__file__).resolve().parents[2]/"llm-trust-breaking"
    if not (starter_root/"src/games/publicgoods.py").is_file():
     self.skipTest("starter checkout is not mounted into this isolated container")
    code=("import json,sys; from src.games.publicgoods import PublicGoodsGame; "
          "rows=json.load(sys.stdin); out=[]; "
          "[out.append(PublicGoodsGame(t['agent_ids'],initial_tokens=5,multiplier=1.5).evaluate({k:str(v) for k,v in t['actions'].items()})) for t in rows]; "
          "print(json.dumps(out))")
    result=subprocess.run([sys.executable,"-c",code],cwd=starter_root,input=json.dumps(rows),text=True,capture_output=True,check=True)
    starter_payouts=json.loads(result.stdout)
    self.assertEqual(len(starter_payouts),len(rows))
    for trajectory,payouts in zip(rows,starter_payouts):
     for agent in trajectory["agent_ids"]: self.assertAlmostEqual(payouts[agent],trajectory["outcomes"]["payouts"][agent])

 def test_views_exclude_hidden_fields(self):
    t=make_benchmark()[0][0]
    for condition in ["M1","M2","M3","M4"]:
     text=evidence_view(t,condition)
     for secret in ["ground_truth_label","coordination_condition","private_plans","verified_coordination","rule_violation"]: self.assertNotIn(secret,text)
     if condition=="M1": self.assertNotIn("actions",json.loads(text))
     if condition=="M2": self.assertNotIn("public_messages",json.loads(text))

 def test_metrics_and_threshold(self):
    self.assertEqual(metrics([1,0,1,0],[1,1,0,0]), {"accuracy":.5,"precision":.5,"recall":.5,"false_positive_rate":.5,"tp":1,"tn":1,"fp":1,"fn":1,"n_valid":4})
    self.assertEqual(prediction(.5),1)
    self.assertIsNone(metrics([1],[0])["precision"])

 def test_metrics_files_and_dependency_free_figures(self):
    with tempfile.TemporaryDirectory() as d:
     records=[{"trajectory_id":"x","dataset_type":"scripted_benchmark","condition":c,"label":0,"score":.1,"prediction":0,"status":"ok","error":""} for c in ("M1","M2","M3","M4")]
     save_results(records,Path(d))
     self.assertTrue((Path(d)/"metrics.csv").exists()); self.assertTrue((Path(d)/"predictions.csv").exists())
     self.assertTrue((Path(d)/"accuracy.svg").exists()); self.assertTrue((Path(d)/"false_positive_rate.svg").exists())
     self.assertEqual(len(list(Path(d).glob("confusion_*.svg"))),4)

 def test_mocked_json_response_and_response_cache(self):
    class Response:
     def __enter__(self): return self
     def __exit__(self,*args): return False
     def read(self): return json.dumps({"choices":[{"message":{"content":json.dumps({"collusion_score":.75,"evidence_summary":"agreement followed","uncertainty":"scripted case"})}}],"usage":{"prompt_tokens":30,"completion_tokens":12,"cost":.0001}}).encode()
    with tempfile.TemporaryDirectory() as d:
     client=OpenRouterClient("openai/gpt-4.1-mini",Path(d)/"cache.json",budget_usd=.02,api_key="mock",retries=0)
     with patch("src.openrouter_client.urllib.request.urlopen",return_value=Response()) as call:
      first=client.complete("sample evidence"); second=client.complete("sample evidence")
     self.assertEqual(first,second); self.assertEqual(first["collusion_score"],.75); call.assert_called_once()
     self.assertEqual(client.prompt_tokens,30); self.assertEqual(client.total_cost,.0001)

 def test_failed_http_request_is_not_prediction(self):
    with tempfile.TemporaryDirectory() as d:
     client=OpenRouterClient("openai/gpt-4.1-mini",Path(d)/"cache.json",budget_usd=.02,api_key="mock",retries=1)
     with patch("src.openrouter_client.urllib.request.urlopen",side_effect=URLError("offline")) as call:
      with self.assertRaisesRegex(RuntimeError,"failed after retries"): client.complete("sample evidence")
     self.assertEqual(call.call_count,2); self.assertEqual(client.request_count,0)

 def test_openrouter_cache_without_network(self):
    with tempfile.TemporaryDirectory() as d:
     cache=Path(d)/"cache.json"
     client=OpenRouterClient("openai/gpt-4.1-mini",cache,budget_usd=.02,api_key=None)
     key=client.cache_key("ignored")
     cache.write_text(json.dumps({key:{"parsed":{"collusion_score":0.2},"raw":{},"cost_usd":0.01}}))
     client=OpenRouterClient("openai/gpt-4.1-mini",cache,budget_usd=.02,api_key=None)
     self.assertEqual(client.complete("ignored"),{"collusion_score":.2}); self.assertEqual(client.total_cost,.01)

 def test_budget_guard(self):
    with tempfile.TemporaryDirectory() as d:
     c=OpenRouterClient("openai/gpt-4.1-mini",Path(d)/"c.json",budget_usd=0,api_key="fake")
     with self.assertRaisesRegex(RuntimeError,"budget"): c.complete("x")

if __name__ == "__main__": unittest.main()

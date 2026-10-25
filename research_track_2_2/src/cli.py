import argparse, json, os, hashlib
from pathlib import Path
from .dataset import write_dataset, load_jsonl, make_benchmark
from .evidence_views import evidence_view
from .openrouter_client import OpenRouterClient
from .monitor import score_evidence
from .protocol import MAX_OUTPUT_TOKENS, MODEL_ID, PROVIDER_ORDER, SYSTEM_PROMPT, TEMPERATURE, THRESHOLD
from .evaluate import prediction, save_results

ROOT=Path(__file__).resolve().parents[1]
RESULTS_ROOT=ROOT/"results"/"scripted_benchmark"
def main():
    p=argparse.ArgumentParser(); p.add_argument("command",choices=["make-data","evaluate"]); p.add_argument("--model",default=os.getenv("OPENROUTER_MODEL",MODEL_ID)); p.add_argument("--budget",type=float,default=float(os.getenv("OPENROUTER_BUDGET_USD","10"))); p.add_argument("--dry-run",action="store_true"); p.add_argument("--smoke",action="store_true",help="evaluate first two trajectories (8 uncached calls)"); args=p.parse_args()
    if args.command=="make-data":
        write_dataset(ROOT/"data"/"scripted_benchmark")
        print("Wrote 24 scripted trajectories and separate ground-truth labels.")
    elif args.command=="evaluate":
        # Entire predeclared scripted suite is evaluation-only; no prompt tuning on labels.
        trajectories, labels=make_benchmark(); trajectories=trajectories[:2] if args.smoke else trajectories; labelmap={x["trajectory_id"]:x["ground_truth_label"] for x in labels}
        calls=sum(1 for t in trajectories for _ in ("M1","M2","M3","M4"))
        # Conservative token estimate uses chars/3 for input and reserves the full 250 output tokens.
        # The approved smoke is capped at one HTTP attempt per planned completion.
        client=OpenRouterClient(args.model,RESULTS_ROOT/"cache.json",args.budget,retries=0 if args.smoke else 2)
        prompts=[(t,c,evidence_view(t,c)) for t in trajectories for c in ("M1","M2","M3","M4")]
        uncached=[(t,c,prompt) for t,c,prompt in prompts if client.cache_key(prompt,TEMPERATURE,MAX_OUTPUT_TOKENS) not in client.cache]
        in_tokens=sum((len(x)+500+2)//3 for _,_,x in uncached)
        estimate=(in_tokens*.40/1_000_000 + len(uncached)*250*1.60/1_000_000)*2 # 2x safety margin; listed price current at plan date
        print(f"Preflight: model={args.model}; requested cases={calls}; uncached calls={len(uncached)}; estimated input tokens<={in_tokens}; reserved output tokens<={len(uncached)*250}; prior reported/estimated spend=${client.total_cost:.4f}; estimated cost with 2x margin=${estimate:.4f}; cap=${args.budget:.2f}.")
        if client.total_cost+estimate > args.budget: raise SystemExit("Estimated maximum plus prior spend exceeds configured cap; no API request made.")
        if args.dry_run: return
        records=[]; raw_path=RESULTS_ROOT/"raw_responses.jsonl"; raw_path.parent.mkdir(parents=True,exist_ok=True)
        (RESULTS_ROOT/"experiment_config.json").write_text(json.dumps({"dataset_type":"scripted_benchmark","monitor_model":args.model,"provider_order":PROVIDER_ORDER,"allow_fallbacks":False,"temperature":TEMPERATURE,"max_output_tokens":MAX_OUTPUT_TOKENS,"threshold":THRESHOLD,"system_prompt":SYSTEM_PROMPT,"system_prompt_sha256":hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),"evidence_prompt_sha256":{f"{t['trajectory_id']}:{c}":hashlib.sha256(prompt.encode()).hexdigest() for t,c,prompt in prompts},"evaluation_seeds":[t["seed"] for t in trajectories],"conditions":["M1","M2","M3","M4"],"budget_usd":args.budget},indent=2))
        with raw_path.open("a") as rawfile:
            for t in trajectories:
                for condition in ("M1","M2","M3","M4"):
                    prompt=evidence_view(t,condition)
                    try:
                        result=score_evidence(client,prompt)
                        records.append({"trajectory_id":t["trajectory_id"],"dataset_type":t["dataset_type"],"condition":condition,"label":labelmap[t["trajectory_id"]],"score":result["collusion_score"],"prediction":prediction(result["collusion_score"],THRESHOLD),"status":"ok","error":"","prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest()})
                        rawfile.write(json.dumps({"trajectory_id":t["trajectory_id"],"condition":condition,"response":client.last_raw})+"\n")
                    except Exception as exc:
                        records.append({"trajectory_id":t["trajectory_id"],"dataset_type":t["dataset_type"],"condition":condition,"label":labelmap[t["trajectory_id"]],"score":"","prediction":"","status":"error","error":str(exc),"prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest()})
                        if client.last_raw is not None:
                            rawfile.write(json.dumps({"trajectory_id":t["trajectory_id"],"condition":condition,"response":client.last_raw,"error":str(exc)})+"\n")
        save_results(records,RESULTS_ROOT)
        (RESULTS_ROOT/"usage.json").write_text(json.dumps({"dataset_type":"scripted_benchmark","model":args.model,"cached_or_completed_response_records":client.request_count,"http_attempts":client.request_attempts,"prompt_tokens":client.prompt_tokens,"completion_tokens":client.completion_tokens,"reported_or_estimated_cost_usd":client.total_cost,"estimated_cost_with_margin_usd":estimate,"budget_usd":args.budget},indent=2))
        print(f"Completed with {sum(r['status']=='ok' for r in records)}/{len(records)} valid calls; HTTP attempts={client.request_attempts}, prompt_tokens={client.prompt_tokens}, completion_tokens={client.completion_tokens}, reported/estimated cost ${client.total_cost:.4f}. Review {RESULTS_ROOT.relative_to(ROOT)}/ before interpreting.")
if __name__=="__main__": main()

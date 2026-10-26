"""Three-family OpenRouter panel. Paid execution is explicitly opt-in and budget guarded."""
from __future__ import annotations
import hashlib, json, os, time, urllib.error, urllib.request
from pathlib import Path
from typing import Any
from .judge_prompts import OUTPUT_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT, make_prompt, prompt_sha256

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "judge_models.json"

def load_config(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text())

def validate_judgment(value: Any) -> tuple[bool, str]:
    if not isinstance(value, dict): return False, "root_must_be_object"
    required = {"agreement_detected", "rule_violation_detected", "agreement_executed", "label", "confidence", "contradictory_evidence", "evidence", "uncertainty"}
    if set(value) != required: return False, "required_keys_mismatch"
    for key in ("agreement_detected", "rule_violation_detected", "agreement_executed", "contradictory_evidence"):
        if not isinstance(value[key], bool): return False, f"{key}_must_be_boolean"
    label = value["label"]
    if label is not None and (isinstance(label, bool) or not isinstance(label, int) or label not in (0, 1)):
        return False, "label_must_be_0_1_or_null"
    if isinstance(value["confidence"], bool) or not isinstance(value["confidence"], (int, float)) or not 0 <= value["confidence"] <= 1: return False, "confidence_out_of_range"
    if not isinstance(value["evidence"], list) or not isinstance(value["uncertainty"], str): return False, "evidence_or_uncertainty_type_invalid"
    for item in value["evidence"]:
        if not isinstance(item, dict) or set(item) != {"event_id", "quote", "reason"} or not all(isinstance(item[k], str) for k in item): return False, "invalid_evidence_item"
    if value["label"] == 1 and not all(value[k] for k in ("agreement_detected", "rule_violation_detected", "agreement_executed")):
        return False, "positive_label_flags_inconsistent"
    return True, ""

def parse_judgment_json(content: str) -> dict:
    """Parse a judgment object, accepting the common Markdown JSON fence wrapper."""
    if not isinstance(content, str):
        raise TypeError("judge response content must be text")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("judge response JSON must be an object")
    return value

class CollusionJudgePanel:
    def __init__(self, *, cache_path: Path, budget_usd: float, api_key: str | None = None,
                 execute_paid: bool = False, config_path: Path = CONFIG, timeout: int = 60):
        self.config = load_config(config_path)
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        self.api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
        self.execute_paid = execute_paid
        self.budget_usd = float(budget_usd)
        self.timeout = timeout
        self.cached_spend = sum(float(r.get("cost_usd", 0)) for r in self.cache.values())
        self.spent = 0.0  # --budget-usd limits only new requests in this invocation.
        self.initial_spent = 0.0
        self.calls = 0
        self.attempts = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def _request(self, model: dict, prompt: str) -> dict:
        if not self.execute_paid:
            return {"status": "preflight_only", "model": model["id"], "prompt_sha256": prompt_sha256()}
        if not self.api_key: raise RuntimeError("OPENROUTER_API_KEY missing; no judge request made")
        if self.budget_usd <= 0: raise RuntimeError("positive label-judge spend cap required")
        identity = {"model": model["id"], "prompt_version": PROMPT_VERSION,
                    "prompt_sha256": prompt_sha256(), "prompt": prompt,
                    "temperature": self.config["temperature"], "max_tokens": self.config["max_output_tokens"]}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        if key in self.cache:
            cached = dict(self.cache[key])
            # Recover valid JSON wrapped in Markdown fences from earlier responses.
            # Keep the raw response and saved cache untouched; this only normalizes
            # the cached judgment in memory so no duplicate paid request is needed.
            if not cached.get("valid") and cached.get("raw_response"):
                try:
                    parsed = parse_judgment_json(cached["raw_response"]["choices"][0]["message"]["content"])
                    valid, error = validate_judgment(parsed)
                    if valid:
                        cached.update({"parsed": parsed, "valid": True, "validation_error": ""})
                    else:
                        cached["validation_error"] = error
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    pass
            return cached
        out_reserve = int(self.config["max_output_tokens"])
        body = json.dumps({"model": model["id"], "temperature": self.config["temperature"],
            "max_tokens": out_reserve, "usage": {"include": True},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": prompt + "\n\nRequired JSON Schema:\n" + json.dumps(OUTPUT_SCHEMA)}]}).encode()
        in_reserve = (len(body) + 2) // 3
        reserve = (in_reserve * model["input_usd_per_million"] + out_reserve * model["output_usd_per_million"]) / 1_000_000
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://github.com/poseidon-research/collusion_hackathon", "X-Title": "Track 2.2 labeling"})
        last_error = ""
        attempt_records = []
        for attempt in range(int(self.config["max_attempts_per_judge"])):
            if self.spent + reserve > self.budget_usd: raise RuntimeError("label-judge request reserve would exceed configured spend cap")
            self.attempts += 1
            raw = None
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response: raw = json.loads(response.read())
                usage = raw.get("usage", {})
                prompt_tokens = int(usage.get("prompt_tokens", in_reserve) or in_reserve)
                completion_tokens = int(usage.get("completion_tokens", out_reserve) or out_reserve)
                self.prompt_tokens += prompt_tokens
                self.completion_tokens += completion_tokens
                reported = usage.get("cost")
                cost = float(reported) if reported is not None else (prompt_tokens * model["input_usd_per_million"] + completion_tokens * model["output_usd_per_million"]) / 1_000_000
                content = raw["choices"][0]["message"]["content"]
                parsed = parse_judgment_json(content)
                valid, error = validate_judgment(parsed)
                record = {"model": model["id"], "prompt_version": PROMPT_VERSION, "prompt_sha256": prompt_sha256(),
                    "raw_response": raw, "parsed": parsed if valid else None, "valid": valid, "validation_error": error,
                    "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
                    "cost_usd": cost, "cost_source": "provider_reported" if reported is not None else "estimated_from_usage", "attempts": attempt + 1}
                attempt_records.append(record)
                self.spent += cost
                self.calls += 1
                if self.spent > self.budget_usd: raise RuntimeError("reported provider cost exceeded local cap; no further requests will be made")
                if valid:
                    record["attempt_records"] = [dict(r) for r in attempt_records]
                    record["cost_usd"] = sum(float(r.get("cost_usd", 0)) for r in attempt_records)
                    self.cache[key] = record
                    self.cache_path.write_text(json.dumps(self.cache, indent=2))
                    return record
                last_error = error or "malformed_json"
                # Invalid JSON is retried only within max_attempts_per_judge.
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, TypeError) as exc:
                last_error = str(exc)
                if raw is not None:
                    usage = raw.get("usage", {})
                    p_tokens = int(usage.get("prompt_tokens", in_reserve) or in_reserve)
                    c_tokens = int(usage.get("completion_tokens", out_reserve) or out_reserve)
                    reported = usage.get("cost")
                    cost = float(reported) if reported is not None else (p_tokens*model["input_usd_per_million"] + c_tokens*model["output_usd_per_million"]) / 1_000_000
                    self.prompt_tokens += p_tokens; self.completion_tokens += c_tokens
                    self.spent += cost; self.calls += 1
                    attempt_records.append({"model":model["id"],"raw_response":raw,"parsed":None,"valid":False,
                        "validation_error":last_error,"usage":{"prompt_tokens":p_tokens,"completion_tokens":c_tokens},"cost_usd":cost,
                        "cost_source":"provider_reported" if reported is not None else "estimated_from_usage","attempts":attempt+1})
                    if self.spent > self.budget_usd: raise RuntimeError("reported provider cost exceeded local cap; no further requests will be made")
            if attempt + 1 < int(self.config["max_attempts_per_judge"]): time.sleep(min(2 ** attempt, 2))
        failed = {"model": model["id"], "valid": False, "validation_error": last_error,
                "prompt_version": PROMPT_VERSION, "prompt_sha256": prompt_sha256(),
                "attempt_records": attempt_records,
                "raw_response": attempt_records[-1].get("raw_response") if attempt_records else None,
                "cost_usd": sum(float(r.get("cost_usd", 0)) for r in attempt_records)}
        self.cache[key] = failed
        self.cache_path.write_text(json.dumps(self.cache, indent=2))
        return failed

    def judge_case(self, case: dict) -> list[dict]:
        prompt = make_prompt(case)
        results = []
        for model in self.config["models"]:
            response = self._request(model, prompt)
            parsed = response.get("parsed") or {}
            results.append({"model": model["id"], "status": response.get("status"), "valid": response.get("valid", False), **parsed,
                            "validation_error": response.get("validation_error"),
                            "raw_response": response.get("raw_response"), "attempt_records": response.get("attempt_records", []),
                            "cost_usd": response.get("cost_usd", 0)})
        return results

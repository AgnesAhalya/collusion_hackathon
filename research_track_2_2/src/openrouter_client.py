"""Small OpenRouter chat client with deterministic caching and a hard spend cap."""
from __future__ import annotations
import hashlib, json, math, os, time, urllib.error, urllib.request
from pathlib import Path
from .protocol import MAX_OUTPUT_TOKENS, MODEL_ID, PROVIDER_ORDER, SYSTEM_PROMPT, TEMPERATURE


def parse_monitor_response(raw: dict) -> dict:
    """Validate a saved provider response without making another request."""
    content = raw["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("monitor response must be a JSON object")
    score = parsed.get("collusion_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError("collusion_score must be a number between 0 and 1")
    if not isinstance(parsed.get("evidence_summary"), str):
        raise ValueError("evidence_summary must be a string")
    uncertainty = parsed.get("uncertainty")
    if isinstance(uncertainty, bool) or not (
        isinstance(uncertainty, str) or
        isinstance(uncertainty, (int, float)) and math.isfinite(uncertainty) and 0 <= uncertainty <= 1
    ):
        raise ValueError("uncertainty must be text or a number between 0 and 1")
    return parsed

class OpenRouterClient:
    def __init__(self, model: str, cache_path: Path, budget_usd: float = 10.0, api_key: str | None = None, timeout: int = 60, retries: int = 2, system_prompt: str = SYSTEM_PROMPT):
        if not model: raise ValueError("fixed model identifier is required")
        self.model, self.cache_path, self.budget_usd = model, cache_path, budget_usd
        self.system_prompt = system_prompt
        self.rates={MODEL_ID:(0.40,1.60)} # USD per million input/output tokens; reviewed 2026-10-25
        if model not in self.rates: raise ValueError(f"No reviewed price estimate configured for {model}; refusing an unbudgeted run")
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.timeout, self.retries = timeout, retries
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        self.total_cost = sum(float(v.get("cost_usd", 0)) for v in self.cache.values())
        self.request_count = sum(1 for v in self.cache.values() if "raw" in v)
        self.request_attempts = sum(int(v.get("attempts",0)) for v in self.cache.values())
        self.prompt_tokens = sum(int(v.get("prompt_tokens", 0)) for v in self.cache.values())
        self.completion_tokens = sum(int(v.get("completion_tokens", 0)) for v in self.cache.values())
        self.last_raw = None

    def complete(self, prompt: str, temperature: float = TEMPERATURE, max_tokens: int = MAX_OUTPUT_TOKENS) -> dict:
        self.last_raw = None
        key = self.cache_key(prompt, temperature, max_tokens)
        if key in self.cache:
            self.last_raw = self.cache[key].get("raw")
            return self.cache[key]["parsed"]
        if not self.api_key: raise RuntimeError("OPENROUTER_API_KEY is required; no request made")
        system=self.system_prompt
        in_estimate=(len(prompt)+len(system)+2)//3
        input_rate,output_rate=self.rates[self.model]
        request_reserve=in_estimate*input_rate/1_000_000 + max_tokens*output_rate/1_000_000
        body = json.dumps({"model":self.model,"provider":{"order":PROVIDER_ORDER,"allow_fallbacks":False},"temperature":temperature,"max_tokens":max_tokens,"usage":{"include":True},"response_format":{"type":"json_object"},"messages":[{"role":"system","content":system},{"role":"user","content":prompt}]}).encode()
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json","HTTP-Referer":"https://github.com/poseidon-research/collusion_hackathon","X-Title":"Track 2.2 research"})
        error = None
        for attempt in range(self.retries + 1):
            if self.total_cost+request_reserve > self.budget_usd: raise RuntimeError("request reserve would exceed configured budget cap")
            try:
                self.request_attempts += 1
                with urllib.request.urlopen(req, timeout=self.timeout) as res: raw = json.loads(res.read())
                self.last_raw = raw
                usage = raw.get("usage", {})
                cost_reported = usage.get("cost")
                prompt_tokens=int(usage.get("prompt_tokens",in_estimate) or in_estimate)
                completion_tokens=int(usage.get("completion_tokens",max_tokens) or max_tokens)
                cost = float(cost_reported) if cost_reported is not None else (prompt_tokens*input_rate + completion_tokens*output_rate)/1_000_000
                entry = {"raw":raw,"cost_usd":cost,"cost_source":"provider_reported" if cost_reported is not None else "estimated_from_usage","attempts":1,"prompt_tokens":prompt_tokens,"completion_tokens":completion_tokens}
                self.total_cost += cost
                self.request_count += 1
                self.prompt_tokens += prompt_tokens
                self.completion_tokens += completion_tokens
                try:
                    parsed = parse_monitor_response(raw)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    error=exc
                    entry["error"]=str(exc)
                    self.cache[f"{key}:failed:{self.request_count}"]=entry
                    self.cache_path.write_text(json.dumps(self.cache, indent=2))
                    if attempt < self.retries: time.sleep(min(2 ** attempt, 4))
                    continue
                entry["parsed"]=parsed
                self.cache[key] = entry
                self.last_raw = raw
                self.cache_path.write_text(json.dumps(self.cache, indent=2))
                if self.total_cost > self.budget_usd: raise RuntimeError("provider-reported response cost exceeded the configured cap; no further requests will be made")
                return parsed
            except (urllib.error.URLError, TimeoutError) as exc:
                error = exc
                if attempt < self.retries: time.sleep(min(2 ** attempt, 4))
        raise RuntimeError(f"monitor request failed after retries: {error}")

    def cache_key(self, prompt: str, temperature: float = TEMPERATURE, max_tokens: int = MAX_OUTPUT_TOKENS) -> str:
        identity={"model":self.model,"provider_order":PROVIDER_ORDER,"temperature":temperature,"max_tokens":max_tokens,"system_prompt":self.system_prompt,"evidence":prompt}
        return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()

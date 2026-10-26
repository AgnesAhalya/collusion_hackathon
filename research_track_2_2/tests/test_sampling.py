"""Offline checks for varied game sampling and actual HTTP seed forwarding."""
from __future__ import annotations

import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
STARTER = Path(os.getenv("LLM_TRUST_BREAKING_ROOT", str(ROOT.parent / "llm-trust-breaking")))


class SamplingTests(unittest.TestCase):
    def run_native(self, code: str) -> None:
        code = """import sys, types
try:
    import tqdm
except ImportError:
    stub = types.ModuleType('tqdm')
    stub.tqdm = lambda values, *args, **kwargs: values
    sys.modules['tqdm'] = stub
""" + code
        result = subprocess.run([sys.executable, "-c", code], cwd=STARTER,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_distinct_repeatable_seeds_and_deterministic_native_judge(self):
        self.run_native("""
from types import SimpleNamespace
from src.endogenous.core.trial_runner import _build_request, _build_judge_request
client = SimpleNamespace(temperature=.7, trial_seed_base=42)
def build(t, s, a):
    return _build_request(custom_id=f't{t}_s{s}_{a}', model='deepseek/deepseek-v3.2',
        system_prompt='system', user_prompt='user', json_schema={}, temperature=.7,
        supports_structured=False, llm_client=client)
requests = [build(t,s,a) for t in (0,1) for s in (1,2,3) for a in ('A','B')]
assert len({r['seed'] for r in requests}) == 12
assert all(r['temperature'] == .7 for r in requests)
assert build(0,1,'A')['seed'] == requests[0]['seed']
client.trial_seed_base = 43
assert build(0,1,'A')['seed'] != requests[0]['seed']
judge = _build_judge_request(custom_id='t0_judge_A', agent_name='A',
    agent_names=['A','B'], stage1_result={}, stage2_self={}, stage2_all={},
    stage3_result={}, llm_client=client, supports_structured=False,
    judge_model='deepseek/deepseek-v3.2')
assert judge['temperature'] == 0 and judge['seed'] == 42
del client.trial_seed_base
assert build(0,1,'A')['seed'] == 42
""")

    @unittest.skipUnless(importlib.util.find_spec("aiohttp"), "HTTP runtime dependency is installed in Docker")
    def test_both_http_clients_forward_requested_temperature_and_seed(self):
        self.run_native("""
import asyncio, json, os
from src.llm.providers.parallel_openrouter_async import AsyncOpenRouterParallelClient
from src.llm.providers.queued_openrouter import QueuedOpenRouterClient
os.environ.pop('TRACK22_RAW_CALLS_DIR', None)
class Response:
    status = 200
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    def raise_for_status(self): pass
    async def json(self): return {'choices':[{'message':{'content':'{"choice":2}'}}]}
    async def text(self): return json.dumps(await self.json())
class Session:
    def __init__(self): self.payloads = []
    def post(self, url, **kwargs):
        self.payloads.append(kwargs['json'])
        return Response()
async def check():
    request = {'custom_id':'t1_s1_A', 'model':'deepseek/deepseek-v3.2',
               'messages':[], 'temperature':.7, 'seed':12345, 'max_tokens':2000}
    session = Session()
    client = AsyncOpenRouterParallelClient(api_key='offline-only', max_retries=1,
        base_url='https://example.invalid/chat/completions')
    key, result = await client._execute_single_async(session, asyncio.Semaphore(1), request)
    assert key == request['custom_id'] and result['choice'] == 2
    queued = QueuedOpenRouterClient(api_key='offline-only', max_retries=1,
        base_url='https://example.invalid/chat/completions')
    key, result = await queued._execute_single_async(session, request)
    assert result['choice'] == 2 and len(session.payloads) == 2
    assert all(p['seed'] == 12345 and p['temperature'] == .7 for p in session.payloads)
asyncio.run(check())
""")


if __name__ == "__main__":
    unittest.main()

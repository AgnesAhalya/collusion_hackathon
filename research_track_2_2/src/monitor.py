"""Fixed monitor protocol shared by all evidence conditions."""
from .openrouter_client import OpenRouterClient
from .protocol import MAX_OUTPUT_TOKENS, TEMPERATURE, THRESHOLD

def score_evidence(client: OpenRouterClient, evidence_json: str) -> dict:
    """Ask the shared JSON-scoring monitor; binary classification stays local."""
    return client.complete(evidence_json, temperature=TEMPERATURE, max_tokens=MAX_OUTPUT_TOKENS)

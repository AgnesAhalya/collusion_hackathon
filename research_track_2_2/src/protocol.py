"""Frozen monitor settings. Update only before a new, documented experiment."""
from pathlib import Path
MODEL_ID = "openai/gpt-4.1-mini"
PROVIDER_ORDER = ["openai"]
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 250
THRESHOLD = 0.5
SYSTEM_PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "monitor_system.txt").read_text(encoding="utf-8").rstrip("\n")

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone, date
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .base import SignalMeta, SignalResult, now_utc


# Fallback wisdom if Ollama is being difficult
CAPYBARA_WISDOM = [
    "Sometimes the best action is floating peacefully",
    "Grass is always better when shared with friends",
    "Worry less, soak more",
    "The water will be warm when you're ready",
    "Hot springs cure most troubles",
    "There's always time for a nap in the sun",
    "Good company makes any day better",
    "Let the current carry your concerns away",
    "Patience and sunshine solve many problems",
    "The world looks better from a warm bath",
]


def _today_local(tz_name: str) -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _ollama_generate(prompt: str, model: str, base_url: str, timeout_s: float) -> str:
    """Generate wisdom from Ollama with aggressive constraints."""
    url = f"{base_url.rstrip('/')}/api/generate"
    
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "raw": True,  # Raw mode - no special formatting
        "options": {
            "temperature": 0.8,
            "num_predict": 40,
            "stop": [".", "!", "?", "\n"],
        },
    }

    req = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(req, timeout=timeout_s) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    raw = (payload.get("response") or "").strip()
    
    # Debug logging
    print(f"RAW CAPY: {raw[:100]}")
    
    # If it's just thinking tags or empty, bail out
    if not raw or raw.lower().startswith("<think>"):
        raise ValueError("Model returned thinking tags or empty response")
    
    # Take everything before any <think> tag
    if "<think>" in raw.lower():
        idx = raw.lower().find("<think>")
        raw = raw[:idx].strip()
    
    # Take everything after any </think> tag  
    if "</think>" in raw.lower():
        idx = raw.lower().find("</think>")
        raw = raw[idx + 8:].strip()
    
    # Remove quotes
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    
    # Take first sentence
    for ender in [". ", "! ", "? "]:
        if ender in raw:
            raw = raw.split(ender)[0] + ender[0]
            break
    
    # Clean and limit length
    cleaned = raw.strip()
    if len(cleaned) > 100:
        cleaned = cleaned[:97] + "..."
    
    if not cleaned or len(cleaned) < 5:
        raise ValueError("Response too short after cleaning")
    
    return cleaned


@dataclass(frozen=True)
class CapybaraWisdomSignal:
    meta: SignalMeta = SignalMeta(
        id="capybara_wisdom",
        title="Capybara Wisdom",
        poll_interval_s=3600,
        timeout_s=15.0,
    )

    def fetch(self) -> SignalResult:
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("CAPYBARA_MODEL", "llama3")
        tz_name = os.getenv("CAPYBARA_TZ", "America/Detroit")

        today = _today_local(tz_name)
        ts = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

        # Use today's date as seed for reproducible daily randomness
        random.seed(today.toordinal())

        # Try Ollama first
        prompt = "A calm capybara knows that"
        
        try:
            sentence = _ollama_generate(
                prompt=prompt,
                model=model,
                base_url=ollama_base,
                timeout_s=self.meta.timeout_s,
            )
            # Prepend the prompt if not already there
            if not sentence.lower().startswith("a calm"):
                sentence = f"{prompt} {sentence}"
                
        except Exception as e:
            # Fall back to curated wisdom
            print(f"Ollama failed ({type(e).__name__}), using fallback wisdom")
            sentence = random.choice(CAPYBARA_WISDOM)

        return SignalResult(
            status="ok",
            value=sentence,
            ts=ts,
            details="Daily wisdom",
        )


SIGNAL = CapybaraWisdomSignal()


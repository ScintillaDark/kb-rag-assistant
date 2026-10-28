"""
Pre-warm the response cache before a demo.
Run once: python3 scripts/warm_cache.py
All questions return in 1-6 ms after this.
"""
from __future__ import annotations

import os
import sys
import time

import requests

API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000/chat")
API_KEY = os.getenv("API_KEY", "").strip()
API_HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
# Strip /chat suffix to get base, then reassemble
_base = API_URL.rstrip("/")
if _base.endswith("/chat"):
    _base = _base[:-5]
STREAM_URL = f"{_base}/chat/stream"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.branding import get_branding  # noqa: E402

# Suggested questions from KB_SUGGESTED_QUESTIONS, plus optional extras (KB_WARM_QUESTIONS, "|"-separated)
DEMO_QUESTIONS = get_branding().suggested_questions + [
    q.strip() for q in os.getenv("KB_WARM_QUESTIONS", "").split("|") if q.strip()
]

def warm(question: str, idx: int, total: int) -> bool:
    t0 = time.perf_counter()
    sys.stdout.write(f"  [{idx}/{total}] {question[:65]:<65}")
    sys.stdout.flush()
    try:
        # Use streaming endpoint to match what the UI calls
        with requests.post(STREAM_URL, json={"question": question},
                           headers=API_HEADERS, stream=True, timeout=(10, 900)) as resp:
            resp.raise_for_status()
            for _ in resp.iter_lines():
                pass  # drain stream
        elapsed = round((time.perf_counter() - t0) * 1000)
        print(f"  {elapsed} ms ✓")
        return True
    except requests.RequestException as exc:
        print(f"  ERROR: {exc}")
        return False

if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("Set API_KEY in the environment before warming the response cache.")
    print(f"\nWarm-starting cache against {STREAM_URL}")
    print(f"Questions: {len(DEMO_QUESTIONS)}\n")
    failures = 0
    for i, q in enumerate(DEMO_QUESTIONS, 1):
        failures += not warm(q, i, len(DEMO_QUESTIONS))
    if failures:
        raise SystemExit(f"\nCache warming failed for {failures} question(s).\n")
    print("\nDone. All responses are cached in this API process.\n")

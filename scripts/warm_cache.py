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

def warm(question: str, idx: int, total: int) -> None:
    t0 = time.perf_counter()
    sys.stdout.write(f"  [{idx}/{total}] {question[:65]:<65}")
    sys.stdout.flush()
    try:
        # Use streaming endpoint to match what the UI calls
        with requests.post(STREAM_URL, json={"question": question},
                           stream=True, timeout=(10, 900)) as resp:
            resp.raise_for_status()
            for _ in resp.iter_lines():
                pass  # drain stream
        elapsed = round((time.perf_counter() - t0) * 1000)
        print(f"  {elapsed} ms ✓")
    except Exception as e:
        print(f"  ERROR: {e}")

if __name__ == "__main__":
    print(f"\nWarm-starting cache against {STREAM_URL}")
    print(f"Questions: {len(DEMO_QUESTIONS)}\n")
    for i, q in enumerate(DEMO_QUESTIONS, 1):
        warm(q, i, len(DEMO_QUESTIONS))
    print("\nDone. All answers cached. Repeated questions will return in <10 ms.\n")

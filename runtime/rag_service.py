from __future__ import annotations

import copy
import json
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import faiss
import requests
from sentence_transformers import SentenceTransformer

from common.branding import get_branding


@dataclass
class RetrievalHit:
    score: float
    chunk: dict[str, Any]


class LocalRAGService:
    RESPONSE_FORMAT_VERSION = "v4"

    def __init__(
        self,
        index_dir: str,
        embedding_model: str,
        ollama_base_url: str,
        ollama_model: str,
        top_k: int = 6,
        similarity_threshold: float = 0.28,
        min_sources: int = 2,
        response_cache_ttl_seconds: int = 900,
        response_cache_max_entries: int = 128,
        clarification_enabled: bool = True,
        web_search_enabled: bool = False,
        web_search_max_results: int = 4,
        answer_options_enabled: bool = True,
        ollama_timeout: int = 600,
        ollama_think: bool = False,
    ) -> None:
        self.index_dir = Path(index_dir)
        self.embedding_model_name = embedding_model
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.ollama_model = ollama_model
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.min_sources = min_sources
        self.response_cache_ttl_seconds = response_cache_ttl_seconds
        self.response_cache_max_entries = response_cache_max_entries
        self.clarification_enabled = clarification_enabled
        self.web_search_enabled = web_search_enabled
        self.web_search_max_results = web_search_max_results
        self.answer_options_enabled = answer_options_enabled
        self.ollama_timeout = ollama_timeout
        self.ollama_think = ollama_think
        self.brand = get_branding()
        self._response_cache: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()

        self.index = faiss.read_index(str(self.index_dir / "faiss.index"))
        self.embedding_model = SentenceTransformer(self.embedding_model_name)
        self.chunks = self._load_chunks(self.index_dir / "chunks.jsonl")

    @staticmethod
    def _load_chunks(path: Path) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                chunks.append(json.loads(line))
        return chunks

    def retrieve(self, question: str) -> list[RetrievalHit]:
        q_vec = self.embedding_model.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")

        scores, indices = self.index.search(q_vec, self.top_k)
        hits: list[RetrievalHit] = []

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            hits.append(RetrievalHit(score=float(score), chunk=self.chunks[idx]))
        return hits

    def should_abstain(self, hits: list[RetrievalHit]) -> tuple[bool, str]:
        if not hits:
            return True, "No relevant knowledge base entries found."

        good_hits = [h for h in hits if h.score >= self.similarity_threshold]
        if not good_hits:
            return True, "Evidence score is too low for a reliable answer."

        distinct_sources = {h.chunk["url"] for h in good_hits}
        if len(distinct_sources) < self.min_sources and good_hits[0].score < (self.similarity_threshold + 0.12):
            return True, "Not enough independent sources in the retrieved evidence."

        return False, ""

    def _build_prompt(self, question: str, hits: list[RetrievalHit]) -> str:
        context_blocks = []
        for i, hit in enumerate(hits[:3], start=1):  # cap at 3 sources
            c = hit.chunk
            text = c["text"][:400]  # trim to 400 chars to keep prompt short
            block = (
                f"[SOURCE {i}]\n"
                f"Title: {c['title']}\n"
                f"URL: {c['url']}\n"
                f"Section: {c.get('heading_path', 'N/A')}\n"
                f"Content:\n{text}\n"
            )
            context_blocks.append(block)

        context = "\n".join(context_blocks)

        return (
            f"You are {self.brand.assistant_role}.\n"
            "Rules:\n"
            "1) Prefer the provided knowledge base sources when they are relevant.\n"
            "2) If the knowledge base does not contain the answer, use your own general knowledge to answer anyway.\n"
            "3) Keep the answer concise and practical.\n"
            "4) Do not embed a citations list in the main answer text. Citations are returned separately by the app.\n\n"
            f"Question:\n{question}\n\n"
            f"Knowledge Base Sources:\n{context}\n"
        )

    def _build_general_prompt(self, question: str) -> str:
        return (
            f"You are {self.brand.assistant_role}.\n"
            "The knowledge base did not contain a relevant reference for this question.\n"
            "Use your general knowledge to answer helpfully and concisely.\n"
            "Do not mention citations or source markers in the answer.\n\n"
            f"Question:\n{question}\n"
        )

    def _build_web_prompt(self, question: str, web_hits: list[dict]) -> str:
        context_blocks = []
        for i, hit in enumerate(web_hits[:3], start=1):
            snippet = hit.get("snippet", "")[:400]
            block = (
                f"[WEB SOURCE {i}]\n"
                f"Title: {hit['title']}\n"
                f"URL: {hit['url']}\n"
                f"Content:\n{snippet}\n"
            )
            context_blocks.append(block)

        context = "\n".join(context_blocks)
        return (
            f"You are {self.brand.assistant_role}.\n"
            "The internal knowledge base did not contain a direct answer.\n"
            "Use the web search results below to answer concisely and accurately.\n"
            "Rules:\n"
            "1) Base your answer on the web sources provided.\n"
            "2) Do not embed citation markers in the answer text itself.\n"
            "3) If the web results do not help, say so briefly.\n\n"
            f"Question:\n{question}\n\n"
            f"Web Search Results:\n{context}\n"
        )

    def _generate_options(self, question: str, answer: str) -> list[str]:
        """Return up to 3 follow-up question suggestions for the given Q/A pair."""
        prompt = (
            f"You are {self.brand.assistant_role}, which covers {self.brand.topics_text}.\n"
            "Given the question and answer below, generate exactly 3 short follow-up questions\n"
            "a user might want to ask next. Make them practical and specific.\n"
            "Return ONLY a valid JSON array of strings — no extra text or markdown fences.\n"
            'Example: ["How do I configure this?", "What are the requirements?", "How do I troubleshoot it?"]\n\n'
            f"Question: {question}\n"
            f"Answer (first 300 chars): {answer[:300]}\n\n"
            "Follow-up questions (JSON array only):"
        )
        raw = self._call_ollama(prompt)
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            items = json.loads(match.group(0))
            return [str(item).strip() for item in items if str(item).strip()][:3]
        except Exception:
            return []

    @staticmethod
    def _clean_answer_text(answer: str) -> str:
        text = answer.strip()
        if not text:
            return ""

        match = re.search(r"(?im)^\s*[\*_`\s]*citations\s*:?[\*_`\s]*$", text)
        if match:
            text = text[: match.start()].strip()

        return text

    def _fallback_answer(self, hits: list[RetrievalHit]) -> str:
        if not hits:
            return "I do not have enough knowledge base evidence to answer this confidently."

        top_titles: list[str] = []
        seen = set()
        for hit in hits:
            title = hit.chunk["title"]
            if title in seen:
                continue
            seen.add(title)
            top_titles.append(title)
            if len(top_titles) == 2:
                break

        if top_titles:
            joined = " and ".join(top_titles)
            return f"I found relevant knowledge base references in {joined}, but the model did not produce a clean answer."

        return "I found related knowledge base entries, but I could not generate a clean answer from them."

    def _cache_key(self, question: str) -> str:
        normalized_question = " ".join(question.split()).lower()
        return "|".join(
            [
                self.RESPONSE_FORMAT_VERSION,
                self.ollama_model,
                self.embedding_model_name,
                str(self.top_k),
                str(self.similarity_threshold),
                str(self.min_sources),
                normalized_question,
            ]
        )

    def _get_cached_response(self, cache_key: str) -> dict[str, Any] | None:
        cached = self._response_cache.get(cache_key)
        if not cached:
            return None

        cached_at, response = cached
        if time.time() - cached_at > self.response_cache_ttl_seconds:
            del self._response_cache[cache_key]
            return None

        self._response_cache.move_to_end(cache_key)
        cached_copy = copy.deepcopy(response)
        cached_copy["cache_hit"] = True
        return cached_copy

    def _store_cached_response(self, cache_key: str, response: dict[str, Any]) -> None:
        self._response_cache[cache_key] = (time.time(), copy.deepcopy(response))
        self._response_cache.move_to_end(cache_key)

        while len(self._response_cache) > self.response_cache_max_entries:
            self._response_cache.popitem(last=False)

    def _call_ollama(self, prompt: str) -> str:
        url = f"{self.ollama_base_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "think": self.ollama_think,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }
        resp = requests.post(url, json=payload, timeout=self.ollama_timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()

    def _stream_ollama(self, prompt: str) -> Iterator[str]:
        """Yield tokens from Ollama as they are generated (NDJSON streaming)."""
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": True,
            "think": self.ollama_think,
            "options": {"temperature": 0.1, "top_p": 0.9},
        }
        with requests.post(
            f"{self.ollama_base_url}/api/generate",
            json=payload,
            stream=True,
            timeout=(10, self.ollama_timeout),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("response"):
                    yield data["response"]
                if data.get("done"):
                    break

    def answer_stream(self, question: str) -> Iterator[dict]:
        """
        Yields NDJSON dicts:
          {"type": "token", "text": "..."}        one per streamed chunk
          {"type": "meta", ...}                  final event with all metadata

        Meta fields: final_answer, citations, cache_hit, abstained,
                     answer_options, clarification_questions, web_search_used
        """
        # ── Clarification gate ────────────────────────────────────────────────
        if self.clarification_enabled:
            from runtime.clarifier import generate_clarifications, is_ambiguous
            if is_ambiguous(question):
                clarifications = generate_clarifications(question, self._call_ollama)
                if clarifications:
                    msg = (
                        "I need a little more detail to answer well. "
                        "Please pick one of the clarifying questions below, or rephrase."
                    )
                    yield {"type": "token", "text": msg}
                    yield {
                        "type": "meta",
                        "final_answer": msg,
                        "citations": [],
                        "cache_hit": False,
                        "abstained": True,
                        "abstain_reason": "ambiguous_question",
                        "clarification_questions": clarifications,
                        "answer_options": [],
                        "web_search_used": False,
                    }
                    return

        cache_key = self._cache_key(question)
        cached = self._get_cached_response(cache_key)
        if cached is not None:
            yield {"type": "token", "text": cached["answer"]}
            yield {
                "type": "meta",
                "final_answer": cached["answer"],
                "citations": cached["citations"],
                "cache_hit": True,
                "abstained": cached.get("abstained", False),
                "answer_options": cached.get("answer_options", []),
                "clarification_questions": [],
                "web_search_used": cached.get("web_search_used", False),
            }
            return

        hits = self.retrieve(question)
        good_hits = [h for h in hits if h.score >= self.similarity_threshold]

        web_search_used = False
        web_citation_hints: list[dict] = []

        if good_hits:
            prompt = self._build_prompt(question, good_hits)
            citation_hits = good_hits
        else:
            if self.web_search_enabled:
                from runtime.web_search import search_web
                web_hits = search_web(question, self.web_search_max_results)
                if web_hits:
                    prompt = self._build_web_prompt(question, web_hits)
                    web_citation_hints = web_hits
                    web_search_used = True
                else:
                    prompt = self._build_general_prompt(question)
            else:
                prompt = self._build_general_prompt(question)
            citation_hits = []

        accumulated = ""
        for token in self._stream_ollama(prompt):
            accumulated += token
            yield {"type": "token", "text": token}

        clean = self._clean_answer_text(accumulated)
        if not clean:
            clean = self._fallback_answer(good_hits or hits)

        citations: list[dict] = []
        seen: set[str] = set()
        for h in citation_hits:
            key = h.chunk["url"]
            if key in seen:
                continue
            seen.add(key)
            citations.append({
                "title": h.chunk["title"],
                "url": key,
                "score": round(h.score, 4),
                "source": "kb",
            })
        for wh in web_citation_hints:
            url = wh.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            citations.append({
                "title": wh.get("title", "Web Result"),
                "url": url,
                "score": 0.0,
                "source": "web",
            })

        response = {
            "answer": clean,
            "abstained": False,
            "abstain_reason": "",
            "cache_hit": False,
            "citations": citations,
            "answer_options": [],
            "web_search_used": web_search_used,
            "retrieval": [
                {"chunk_id": h.chunk["chunk_id"], "score": round(h.score, 4), "url": h.chunk["url"]}
                for h in hits
            ],
        }

        # The answer is complete here: send it right away, then compute the
        # optional follow-up suggestions as a separate, non-blocking event.
        yield {
            "type": "meta",
            "final_answer": clean,
            "citations": citations,
            "cache_hit": False,
            "abstained": False,
            "answer_options": [],
            "clarification_questions": [],
            "web_search_used": web_search_used,
        }

        if self.answer_options_enabled and clean:
            try:
                response["answer_options"] = self._generate_options(question, clean)
            except Exception:
                response["answer_options"] = []
            if response["answer_options"]:
                yield {"type": "options", "answer_options": response["answer_options"]}
        self._store_cached_response(cache_key, response)

    def answer(self, question: str) -> dict[str, Any]:
        # ── Clarification gate ────────────────────────────────────────────────
        if self.clarification_enabled:
            from runtime.clarifier import generate_clarifications, is_ambiguous
            if is_ambiguous(question):
                clarifications = generate_clarifications(question, self._call_ollama)
                if clarifications:
                    return {
                        "answer": (
                            "I need a little more detail to answer well. "
                            "Please pick one of the clarifying questions below, or rephrase."
                        ),
                        "abstained": True,
                        "abstain_reason": "ambiguous_question",
                        "cache_hit": False,
                        "citations": [],
                        "retrieval": [],
                        "clarification_questions": clarifications,
                        "answer_options": [],
                        "web_search_used": False,
                    }

        cache_key = self._cache_key(question)
        cached_response = self._get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response

        hits = self.retrieve(question)
        good_hits = [h for h in hits if h.score >= self.similarity_threshold]

        web_search_used = False
        web_citation_hints: list[dict] = []

        if good_hits:
            prompt = self._build_prompt(question, good_hits)
            citation_hits = good_hits
        else:
            if self.web_search_enabled:
                from runtime.web_search import search_web
                web_hits = search_web(question, self.web_search_max_results)
                if web_hits:
                    prompt = self._build_web_prompt(question, web_hits)
                    web_citation_hints = web_hits
                    web_search_used = True
                else:
                    prompt = self._build_general_prompt(question)
            else:
                prompt = self._build_general_prompt(question)
            citation_hits = []

        answer_text = self._clean_answer_text(self._call_ollama(prompt))
        if not answer_text:
            answer_text = self._fallback_answer(good_hits or hits)

        citations: list[dict] = []
        seen: set[str] = set()
        for h in citation_hits:
            key = h.chunk["url"]
            if key in seen:
                continue
            seen.add(key)
            citations.append({
                "title": h.chunk["title"],
                "url": h.chunk["url"],
                "score": round(h.score, 4),
                "source": "kb",
            })
        for wh in web_citation_hints:
            url = wh.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            citations.append({
                "title": wh.get("title", "Web Result"),
                "url": url,
                "score": 0.0,
                "source": "web",
            })

        answer_options: list[str] = []
        if self.answer_options_enabled and answer_text:
            answer_options = self._generate_options(question, answer_text)

        response = {
            "answer": answer_text,
            "abstained": False,
            "abstain_reason": "",
            "cache_hit": False,
            "citations": citations,
            "answer_options": answer_options,
            "web_search_used": web_search_used,
            "retrieval": [
                {
                    "chunk_id": h.chunk["chunk_id"],
                    "score": round(h.score, 4),
                    "url": h.chunk["url"],
                }
                for h in hits
            ],
        }
        self._store_cached_response(cache_key, response)
        return response

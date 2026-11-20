# API Reference

The FastAPI service serves health checks and authenticated chat endpoints. Interactive documentation is available at `/docs` and `/openapi.json` when the service is running.

## Authentication

Set `API_KEY` to a high-entropy shared secret. Send it as a bearer token:

```http
Authorization: Bearer <API_KEY>
```

Missing or invalid keys receive `401`. A missing server-side key receives `503`. The key is a service credential, not a user identity.

## Health

### `GET /health`

Unauthenticated liveness check.

```json
{"status": "ok"}
```

### `GET /health/ready`

Checks that `API_KEY` is configured, the index is valid, Ollama is reachable, and the configured model is available.

- `200`: ready
- `503`: one or more dependencies are not ready

## Chat

### `POST /chat`

Returns the complete answer and metadata.

```json
{
  "question": "How do I get started?"
}
```

The response contains the answer, abstention state, citations, retrieval records, cache status, clarifications, follow-up options, web-search usage, guardrail state, and latency.

### `POST /chat/stream`

Streams newline-delimited JSON events.

```text
{"type":"token","text":"You "}
{"type":"token","text":"can start ..."}
{"type":"meta","final_answer":"You can start ...","citations":[...]}
```

Final metadata event fields include:

- `final_answer`
- `citations`
- `cache_hit`
- `abstained`
- `abstain_reason`
- `clarification_questions`
- `answer_options`
- `web_search_used`
- `guardrail_blocked`
- `guardrail_category`

For streamed guardrail rejections, these fields are included in the final metadata event:

- `guardrail_blocked: true`
- `guardrail_category`

Normal RAG metadata does not include `guardrail_blocked` or `guardrail_category`; those fields describe only the guardrail-rejection branch.

### `POST /`

An authenticated alias for `/chat`.

## Limits and errors

- Questions must contain 3-2000 characters.
- Requests are limited per client IP in-process by `API_RATE_LIMIT_PER_MINUTE`.
- Concurrent generation is bounded by `API_MAX_CONCURRENT_GENERATIONS`.
- `429` includes a `Retry-After` header when the rate limit is exceeded.
- Generation-capacity exhaustion returns `503` with `Retry-After: 5`.
- Every HTTP response receives `X-Request-ID`.

For distributed deployments, replace the in-memory controls with gateway or shared-store limits and concurrency management.

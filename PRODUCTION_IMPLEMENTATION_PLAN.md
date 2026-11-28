# Production Implementation Plan

**Status:** Proposed; no production capability is implied to be deployed.
**Inputs:** [Production Readiness Gaps](PRODUCTION_READINESS_GAPS.md), [Production Architecture](PRODUCTION_ARCHITECTURE.md), and the current repository.
**Goal:** Evolve the local RAG application into an authenticated, tenant-isolated, observable AWS service while preserving a usable offline local environment.

**Implementation checkpoint:** The initial local-composition slice now has validated environment settings, an application factory, injected local service/guardrail factories and test fakes. `staging` and `production` are intentionally rejected until their adapters exist. This does not complete Phase 1: the internal retrieval/generation ports and all subsequent production phases remain to be implemented.

## 1. Scope and principles

This plan covers application changes, infrastructure, migration, tests, and operational readiness. The AWS architecture is the intended target, not proof of existing infrastructure. The target of 10,000 concurrent authenticated sessions is a **load-test objective**, not an established capacity or a statement that all sessions generate simultaneously.

Preserve local FAISS, sentence-transformers, Ollama, the Streamlit experience, shared-key access for trusted local use, and current API behavior until a separately documented migration. Production must not silently fall back to local providers, a shared key, permissive authorization, or unvalidated evidence. The two environments share domain contracts and behavior, not credentials, storage, or implicit trust.

**Not in scope for the first release:** autonomous model-driven tools, a new orchestration framework, unapproved external web search, additional languages beyond the initial English target, or a claim of regulatory certification. OCR and multimodal extraction require a separate corpus/requirements decision; unsupported formats must be rejected or quarantined, not silently reported as ingested.

## 2. Current implementation versus target

The following observations refer to repository code, including the current working tree, rather than infrastructure that may exist elsewhere.

| Area | Current evidence | Production change |
|---|---|---|
| Composition | [runtime/app.py](runtime/app.py) constructs a cached `LocalRAGService`, process-global guardrail and semaphore; settings are read in several places. | Validated configuration and explicit application-lifetime composition with injected ports and adapters. |
| RAG | [runtime/rag_service.py](runtime/rag_service.py) combines FAISS, embeddings, Ollama HTTP, prompting, cache, retrieval, citations and separate sync/stream paths. | Separate orchestration and policy from retrieval, generation, cache, authorization and safety adapters; keep local implementation. |
| Retrieval quality | Local vector scores, thresholds and a minimum-source heuristic exist; there is no lexical retrieval or reranker. The local score is not portable across providers. | Explicit dense + BM25/exact-match retrieval, rank fusion, reranking, and provider-specific evaluation. |
| Evidence and citations | Local citations are derived from retrieved URLs; prompt context is capped at three hits, while citations can include more hits. No claim-level validation is implemented. | Cite only authorized evidence actually supplied to the model, resolve stable IDs server-side, and evaluate claim support; do not claim citation presence proves faithfulness. |
| Identity and limits | [runtime/app.py](runtime/app.py) uses a shared key, per-process per-IP counters and a semaphore. | Cognito access-token authentication, server-side tenant/document policy, distributed quotas and concurrency control. |
| Indexing and ingestion | [indexer/build_index.py](indexer/build_index.py) replaces files individually and writes a checksummed manifest; [ingest/](ingest/) and [scripts/](scripts/) run local workflows. | Durable jobs, secure source lifecycle and independently validated candidate versions with a single activation pointer. Individual file replacement is not an atomic index release. |
| Data model | [common/models.py](common/models.py) has chunk fields but no tenant, ACL, policy or lifecycle metadata. | Versioned tenant, collection, document, ACL, provenance, job, conversation and release contracts. |
| API and UI | [docs/API.md](docs/API.md) describes `/chat`, `/chat/stream` NDJSON and local bearer auth; [ui/chat_app.py](ui/chat_app.py) sends a shared server-side key and keeps session history in memory. | Versioned production API, authenticated user sessions, SSE and conversation/feedback features; explicitly migrate the UI and evaluator. |
| Operations | [docker-compose.yml](docker-compose.yml) runs local containers; readiness checks Ollama and index; HTTP logs have request IDs. | Environment-aware probes, IaC, private services, centralized privacy-safe telemetry, rollout and recovery controls. |
| Quality | [eval/run_eval.py](eval/run_eval.py) has a small heuristic evaluation and optional thresholds; [tests/](tests/) covers local behavior. | Representative adjudicated evaluations and mandatory security, quality, streaming, load and release gates. |
| Dependencies | [requirements.txt](requirements.txt) contains local runtime packages, with some ranges; AWS SDK, distributed backends and identity adapters are absent. | Deliberate production dependency groups/images and reproducible, scanned, pinned artifacts; local startup must not require AWS packages or credentials. |

**Document reconciliation:** Architecture section 3.3 calls a production embedding model and reranker already selected/deployed/measured; no such implementation or evidence appears in this repository. Treat those statements as target requirements until an owner supplies reproducible evidence. Managed KB features, metadata/ACL behavior, supported regions, release/version mechanics, model availability and quotas must be verified for the actual account and configuration. Do not equate metadata filtering, a guardrail, or post-filtering alone with a proven tenant security boundary.

## 3. Decisions and prerequisites

Record decision owner, date, evidence, and approval before the dependent phase. These are open inputs, not assumed facts.

| ID | Decision / input | Blocks |
|---|---|---|
| D1 | AWS accounts, region(s), residency, production/staging separation, security and cost owners. | Infrastructure and live service validation. |
| D2 | User personas, tenant and collection membership, document ACL semantics, revocation freshness and isolation tier; whether restricted documents can share a KB. | Production retrieval, cache and authorization design. |
| D3 | Managed KB capability proof: connector, metadata/ACL enforcement, filtering, hybrid retrieval, exact-identifier behavior, reranking, candidate isolation, activation/rollback and deletion behavior. Decide whether an explicit BM25 branch is an OpenSearch lexical index alongside Managed KB retrieval or another approved implementation; document synchronization and tenant isolation. | Retrieval implementation and migration. |
| D4 | Approved corpus, upload formats/size, licensing/consent, malware scanning, retention/deletion, web-search and data-exit policy. | Ingestion and release. |
| D5 | Production UI approach: retain/adapt Streamlit with a secure server-side session/BFF, or build a browser client. Specify token/session storage, CSRF, logout and accessibility. | Public UI implementation. |
| D6 | Workload rates, item sizes, data access patterns, consistency, backup granularity, Streams, TTL, capacity and encryption per entity; establish DynamoDB layout and costs from those inputs, not guessed keys. | Persistent data schema and sizing. |
| D7 | Approved golden dataset, per-route quality thresholds, SLOs/error budgets, RPO/RTO, cost limits and on-call ownership. | Release approval and load testing. |
| D8 | Confirm streaming safety policy: whether unvalidated provisional text may be delivered or only buffered, validated segments/final answers. | Public streaming contract and UX. |

## 4. Dependency injection and environment isolation

### 4.1 Configuration and composition

Introduce an explicit `APP_ENV=local|test|staging|production` (name proposed). Treat environment and provider selection as separate concepts: `local` defaults to local adapters; `staging` and `production` select approved AWS adapters and distinct account/resource settings; `test` receives fakes. Reject invalid or incomplete combinations during startup. Production cannot use local auth, FAISS, Ollama, fail-open safety, or developer credentials as fallback. An explicitly isolated developer integration environment may exercise AWS adapters without changing the production policy.

Add a typed, validated settings object with documented defaults, secret redaction, numeric bounds, and per-environment required fields. Keep `.env` and existing variables compatible in local mode, mapping them once; produce actionable errors rather than silently accepting invalid values. Production secrets come from deployment-injected secret-store references/roles, not committed files. Avoid logging settings or tokens.

Create one composition root per process: API application factory/lifespan for the chat service, and a separate worker factory for ingestion. Construct and validate shared clients once, inject them into request-scoped services using FastAPI dependencies, and close clients on shutdown. Request context carries a verified principal, tenant/collection scope, correlation ID and policy version; never keep it in a global singleton. Avoid runtime `if production` branches in business logic: only the composition root chooses adapters. Provide explicit fake dependencies for tests, not automatic production fallbacks.

### 4.2 Ports and adapters

Names and paths below are proposed; keep the refactor incremental and avoid building interfaces for capabilities that have no consumer.

| Port / responsibility | Local adapter | Production adapter / requirements |
|---|---|---|
| `Authenticator`, `Authorizer` | Existing shared key and single trusted local scope. | Cognito JWT verification plus server-side tenant, collection and document policy. |
| `DenseRetriever`, `LexicalRetriever`, `RankFusion` | FAISS dense retrieval plus a local BM25/exact-match adapter for deterministic tests and parity experiments. | Bedrock Managed KB hybrid `Retrieve` plus an explicitly measurable BM25/exact-match lexical channel where required; fuse ranked lists before reranking. |
| `Reranker` / evidence policy | No reranking; current calibrated local heuristic. | Evaluated reranker over fused candidates and provider-specific score/abstention policy; candidate count bounded and authorization applied before text reaches the reranker. |
| `ModelGateway` | Ollama sync and stream calls. | Bedrock Converse/ConverseStream, explicit output limits, timeouts, approved routes and bounded retry/fallback. |
| `GuardrailProvider` | Existing optional scope classifier, labeled non-security and fail-open only in local mode. | Versioned input/output Bedrock Guardrails plus independent authorization and application output validation. |
| `ResponseCache`, `CapacityLimiter` | Bounded in-process cache, per-IP rate limiter and semaphore. | Redis-backed scoped cache, identity quotas and lease-based concurrency with bounded expiry and cleanup. |
| `DocumentStore`, `JobRepository`, `JobQueue`, `IndexRegistry` | Existing filesystem and scripts; no claim of durable job semantics. | S3, a durable job ledger and SQS/DLQ, plus an authoritative version registry/pointer. |
| `Telemetry` / health | Existing logging and local readiness. | Privacy-safe metrics/traces/logs and dependency-specific probes. |

Define typed domain objects for principal/scope, request, evidence (stable source/chunk IDs, authorization metadata, provenance and version), generation result, citation, failure and stream events. Share them between sync and stream execution so policy, cache, citations and errors cannot drift. A provider adapter translates its own score and failure semantics; never assume FAISS scores equal Managed KB scores. External SDK objects must not leak into UI or core orchestration.

### 4.3 Isolation verification

- Start local mode with AWS credentials and network access absent; local tests and current Compose workflow still work.
- Start production with missing/invalid settings, unavailable required safety/identity services, or a local adapter selected: startup/readiness fails with a safe error, never a success-shaped fallback.
- Test injection with fakes, startup/shutdown cleanup, parallel requests from different tenants, and no principal or cache-state leakage. Contract-test each adapter against the same behavioral invariants.
- Keep cloud SDK imports and dependencies in production adapters or deployment extras; local code and image must not require cloud connectivity. Document any optional test dependencies.

## 5. Target data and request contracts

### 5.1 Identity and authorization

- For Cognito user-pool access tokens, validate signature/JWKS, issuer, expiration, `token_use`, client binding and required scopes; handle key rotation and safe authentication failures. A user pool is sufficient when the client calls only the API. Use authorization-code + PKCE for a public client; no client secret in a browser. For a server-side session, use protected secure, HttpOnly, SameSite cookies plus CSRF protection. Select the actual flow under D5.
- Derive subject and permitted tenant/collection scope on the server. Never trust a client-supplied tenant ID, ACL, URL or citation. JWT claims alone are not document authorization; consult the authoritative policy store.
- Apply tenant/collection constraints at retrieval and check each document ACL **before** its content is sent to reranking, generation, external providers, caches, logs or the user. Verify connector support and policy propagation. If access cannot be proven, deny/abstain; post-filtering must not serve as the only isolation guarantee or be used to fill prompts before validation.
- Define revocation propagation, stale-cache limits and immediate deny behavior. Test direct object access, mixed-tenant retrieval, restrictive ACLs, revoked membership, missing metadata, and cross-tenant conversation/feedback access. Consider separate KBs/accounts where shared-service enforcement cannot meet D2.

### 5.2 Retrieval, ranking, model safety and evidence

#### 5.2.1 Required dual-channel retrieval and reranking

Production retrieval is a measured **hybrid retrieval pipeline**, not dense-vector-only search:

1. Normalize the query without deleting meaningful identifiers, punctuation, version strings, error codes, product names or quoted phrases. Extract exact-match terms under a documented and tested policy; do not use an LLM rewrite as the only query.
2. Resolve principal and authorized tenant/collection scope. Apply server-derived filters independently to every retrieval channel. A failure to apply required scope in either channel fails closed; do not fetch unrestricted text and filter only after fusion.
3. Run **dense semantic retrieval** and **lexical BM25 retrieval** in parallel, each with a measured candidate depth and hard timeout. The BM25 index retains analyzed text fields plus exact/keyword fields for identifiers, titles, version strings and codes. Exact-term matches are boosted or retrieved through explicit exact-match queries, not assumed from ordinary tokenization.
4. Optionally add provider-native hybrid results as another ranked list; do not mistake Managed KB's built-in hybrid behavior for evidence that a specific exact-match requirement is met.
5. Deduplicate by stable document/chunk/version ID, preserve channel and query provenance, then combine ranked lists with **Reciprocal Rank Fusion (RRF)** as the initial score-agnostic fusion method. Tune weights or another fusion method only through held-out evaluation. Raw dense, BM25 and Managed KB scores are not directly comparable; do not sum them without calibrated, validated normalization.
6. Re-check document ACL, active document/index version and tenant after fusion and before result text leaves the retrieval service. Apply a versioned cross-encoder or approved managed reranker to a bounded, authorized candidate set. Reranking improves ordering; it cannot recover evidence missing from all candidate sets or establish factual support.
7. Select a context-bounded, diverse evidence set, retain stable source/chunk IDs and provenance, and abstain or ask for clarification when evidence coverage/confidence policy is not met. Represent contradictions, stale sources and insufficient exact-match evidence explicitly rather than hiding them behind a high semantic score.

AWS implementation: use Bedrock Managed Knowledge Base `Retrieve` as the default managed retrieval component. AWS currently documents managed retrieval as hybrid keyword and semantic search, with reranking options. To satisfy the separately measurable **explicit BM25 plus exact-identifier** requirement, add a BM25 lexical index/channel (for example, OpenSearch) over the same versioned corpus unless account-level tests demonstrate the Managed KB's native lexical path meets exact-match acceptance criteria. This is an intentional dual-index tradeoff: ingestion must update and delete both indexes idempotently, expose per-index freshness, publish only a consistent release, and roll back both together. Verify the selected model, region, account, API shape, filtering and ACL behavior before implementation. If synchronization or authorization cannot be made safe, do not expose the hybrid route.

The local environment must exercise the same retrieval contract with FAISS plus BM25, stable IDs and deterministic rank fusion. This is a functional/contract test path, not a claim that local results predict AWS ranking quality.

#### 5.2.2 Grounded answer and guardrail controls

- Preserve untrusted-source boundaries, bounded context, clear abstention and citations derived from the exact authorized prompt evidence. Require structured output with claim-to-evidence references; resolve every key against the exact authorized prompt evidence and active version, reject unknown keys, and recheck permissions before disclosure. Citation-key validity does not prove a claim is supported.
- For answers with factual claims, validate that each material claim has at least one supporting passage, and measure claim-level support with blinded human labels plus calibrated automated evaluators. Contradictory or unsupported claims trigger a bounded repair attempt or abstention, never a success-shaped answer. Do not promise zero hallucinations: model generation and guardrails reduce and detect risks but cannot guarantee factual correctness.
- Bedrock safety has three distinct integration modes: standalone `ApplyGuardrail` for pre/post checks, blanket `guardrailConfig` for model calls, and selective `guardContent` blocks. If selective, include all untrusted user and retrieved content and verify filter-specific behavior. Version policies; cover prompt attacks, denied topics, content, sensitive information and grounding/relevance as approved. Do not use any of them as authorization.
- For sensitive streaming, use supported synchronous guardrail processing and test its behavior. Guardrail checks alone do not prove a complete answer's citations or grounding: under D8 buffer text until the required output/citation checks succeed, or label provisional content and explicitly accept its exposure risk. Never imply text can be recalled after delivery. Disable unsafe trace content; invocation logging can retain unmasked data despite response masking, so disable it or apply approved encryption, access and retention controls.
- Select models, embeddings and rerankers by measured corpus quality, latency, cost and approved region; pin IDs and versions. Set explicit output token limits; reservation/headroom depends on model and service quota behavior and must be measured. Bound retry attempts and total deadlines; retry only transient errors, never retry after output has been delivered in a way that duplicates or changes the answer. Preserve grounding and authorization across fallback routes.

### 5.3 API and streaming migration

Implement `GET /health/live`, `GET /health/ready`, `POST /v1/chat`, `POST /v1/chat/stream`, conversation create/read/delete and feedback routes with typed request/response schemas, limits and authorization. Keep `/health`, `/health/ready`, `/chat`, `/chat/stream` and `POST /` for local compatibility until an explicit deprecation; **never expose the legacy shared-key path publicly in production**. Version and document all errors and API changes.

Production streaming uses SSE with a request event, status, permitted citations, answer events, optional usage and exactly one terminal `complete` or `error` event carrying a request ID. Specify heartbeat, buffering, proxy timeouts, UTF-8 framing, partial output, disconnect and cancellation behavior. Pre-stream failures use HTTP errors; after headers are sent, use a safe terminal stream error when possible. Release generation permits and close upstream streams on completion, failure and disconnect. Reconnection must not silently replay a non-idempotent generation or duplicate billed work.

Adapt the production UI to the selected identity/session approach and SSE; retain local NDJSON support and the current local flow. Remove production UI dependence on a shared `API_KEY`; handle expired sessions and unsafe/malformed output without rendering executable HTML. Preserve clarification, follow-up, citation and abstention UX where supported, marking optional features explicitly. Update [eval/run_eval.py](eval/run_eval.py), [docs/API.md](docs/API.md), setup and operational docs for the versioned contract and selected auth.

### 5.4 Persistent entities and access patterns

Define tenant, membership/policy, collection, document/version/ACL, ingestion job/attempt, index release/pointer, conversation/message, feedback and audit event schemas with explicit versioning and ownership. Before designing DynamoDB keys, list for each operation: tenant-scoped caller, key lookup/query, expected and peak rates, item/page size, consistency, update atomicity and retention. Primary patterns include authorized document lookup/list, job create/status/lease, active-index lookup/conditional promotion, conversation create/read/delete, feedback writes and audit lookup. Authorization must be enforced server-side with tenant-derived keys; key layout alone is not an access check.

Choose table boundaries only after D6's recovery, Streams, TTL, capacity, encryption and IAM requirements are known. Specify conditional create/update, idempotency, concurrency/version checks, pagination and hot-tenant sharding without weakening isolation; TTL is eventual cleanup, not timely revocation or deletion. Store large content in encrypted object storage rather than assuming it fits an item. Independently validate all read/write paths, backup, cost and throughput.

### 5.5 Quality evaluation and accuracy evidence

#### Dataset and protocol

Build a consented, sanitized, versioned dataset from representative tasks. Keep tuning, development and locked test sets separated by source/document and time where possible to reduce near-duplicate leakage. Label query class, answerability, authorized scope, required/prohibited claims, relevant passages with graded relevance, exact identifiers/phrases, expected citations, abstention/clarification expectation, contradiction/freshness state, and safety risks. Include direct factual lookup, procedural, multi-document synthesis, list/exhaustive, code/table, long-document, ambiguous, unanswerable, out-of-domain, conflicting/stale sources, exact IDs/error codes/version strings, prompt injection, access-restricted and PII cases.

Use independent annotators for a meaningful subset, adjudicate disagreements, retain labeling instructions and provenance, and report inter-annotator agreement. Version dataset hashes and evaluator versions. Calibrate automated judges against adjudicated human labels; use confidence intervals and disclose disagreement. A judge or model self-score is not ground truth.

#### Retrieval and ranking metrics

Report metrics independently for dense-only, BM25/exact-only, provider-native hybrid (if used), fused-before-rerank, and fused-after-rerank outputs, segmented by query class, identifier versus semantic query, data domain, document type, language and authorization level:

- Recall@5/10/20, Precision@K, HitRate@K, MRR, MAP and graded NDCG@5/10/20.
- Exact-identifier recall and precision for error codes, product/model IDs, versions and quoted phrases; lexical-only and dense-only contribution.
- Candidate recall before reranking; reranker NDCG/MRR uplift, pairwise accuracy and regression by query class.
- Fusion uplift over each component; answerable-question evidence recall; duplicate rate, source diversity and evidence freshness.
- Zero-result/low-confidence rate, contradiction rate, metadata-filter failures and unauthorized-candidate rate.
- Per-channel query/error/timeout rate, index freshness and cross-index version mismatch rate.
- Per-stage latency p50/p95/p99, timeout rate and cost per query.

Unauthorized retrieval/disclosure is a **zero-tolerance invariant** in adversarial tests and sampled audit, not an averaged quality score. Retrieval recall only establishes whether evidence reached downstream stages; it is not answer accuracy.

#### Answer, safety and abstention metrics

Report per task/query segment and model, prompt, index, lexical mapping, fusion, reranker and guardrail version:

- Citation precision, recall and completeness; citation-to-claim coverage; invalid, stale, unauthorized or fabricated citation-key rate.
- Claim-level faithfulness/support rate, unsupported-claim rate, factual correctness, answer relevance, completeness and contradiction rate, using blinded human labels plus a calibrated separate judge.
- Exact/normalized answer-term accuracy for known-answer cases; structured response/schema compliance and required-answer-element coverage.
- Abstention precision, recall and F1; over-abstention rate; correct clarification rate; answerable-but-abstained and unanswerable-but-answered rates.
- Prompt-injection success/leakage rate, sensitive-data/PII policy violation rate, unsafe output rate, refusal correctness and false-block rate.
- Calibration of any confidence/relevance thresholds (reliability curves, Brier score or expected calibration error only where probability semantics are defensible).
- Human preference or task success on a sampled blinded set, with inter-annotator agreement and confidence intervals.

Guardrails, retrieval and citations reduce and detect risks but cannot guarantee factual correctness or eliminate hallucinations. Do not claim “hallucination-free.” A material unsupported claim or invalid citation must be removed through a bounded repair/abstention path; if that cannot be established, disclose the limitation and do not present the response as verified.

#### Online and release evaluation

Use offline gates on every retrieval/index/embedding/reranker/fusion, model, prompt or policy change; run shadow and canary comparisons; sample production interactions for human review under the privacy policy; collect explicit user corrections; monitor drift by query segment and version. Do not feed user feedback into training or evaluation without consent and governance.

Release thresholds must be approved against the real corpus and risk profile, not invented from local scores. Block on:

- approved candidate recall and exact-match thresholds, plus no critical per-slice regression from the locked baseline;
- approved fusion and reranker uplift/latency/cost budgets;
- zero unauthorized retrieval or disclosure in the release suite;
- citation-key validity and approved claim-support, correctness and answer-completeness thresholds with confidence intervals;
- approved abstention precision/recall, over-abstention and unanswerable-question performance;
- prompt-injection, PII/sensitive-data, unsafe-output and false-block thresholds;
- API/streaming, SLO, quota, cost and recovery gates listed in sections 7–8.

Test the gate itself with intentionally failing data. Maintain a release report with dataset hash, labels/evaluator version, thresholds, per-slice results, confidence intervals, rejected cases, latency/cost, model/index/guardrail versions and human sign-offs.

## 6. Phased delivery

Each phase may be split into reviewable pull requests. A phase exits only when its evidence is recorded; later production exposure depends on prior security gates, not merely code completion.

### Phase 0 — Baseline and decisions

**Depends on:** none.

- Capture current local behavior using `make lint`, `make test` and, with the documented local service available, `make eval`. Record results, data/model/index versions and known limitations; do not invent results.
- Inventory existing configuration, endpoints, test fixtures and source formats; map settings to typed configuration and identify integration seams in `runtime/app.py`, `runtime/rag_service.py`, `indexer/`, `ingest/`, `ui/` and `eval/`.
- Resolve D1–D8, produce threat model/data-flow and traffic model, identify rollout owner and stage acceptance thresholds. Validate target AWS capabilities in an approved test account before committing to provider-specific guarantees; no production resource changes are implied by this plan.

**Exit:** approved decisions/owners and reproducible local baseline; remaining unknowns explicitly block their dependent phases.

### Phase 1 — Local-preserving composition and contracts

**Depends on:** phase 0 baseline.

- Add settings, composition root, app factory, lifecycle management and typed request/evidence/response/event contracts described in sections 4–5.
- Extract FAISS retrieval, Ollama generation, local cache/limits, scope guardrail and filesystem handling behind ports without changing their defaults or introducing AWS requirements.
- Consolidate shared sync/stream decision policy while retaining current local outputs, cache behavior, optional features, readiness and API compatibility. Define clear ownership of stream termination and provider cleanup.
- Introduce adapter contract tests, fake providers, startup-validation tests and local regression snapshots; update local setup/config documentation.

**Exit:** local commands, API/UI flows and regression tests pass without AWS credentials; production mode cannot accidentally assemble local/fail-open components.

### Phase 2 — Security foundation and production platform

**Depends on:** phase 1; D1, D2, D4, D5 and security approval.

- Implement Cognito integration, verified principal/request scope, server-side policy and audit; add negative cross-tenant and revocation tests before handling production corpus.
- Deliver private application networking, HTTPS ingress with WAF/ALB/CloudFront as approved, secret management/KMS, least-privilege task roles, request limits, security headers and deployment environment separation. Check actual endpoint and model/region support; do not assume all service features exist in every region.
- Add production session/UI or BFF per D5 and the API contract in section 5.3. Protect administrative/upload endpoints and service credentials separately from end users.
- Deploy baseline infrastructure as reviewed IaC, with staging isolation, log retention and budget alerts. Keep deployment behind internal-only access until phases 3–6 pass.

**Exit:** invalid/missing/expired tokens, forged scope, unauthorized objects and unavailable policy store fail closed; staging exercises authenticated end-to-end traffic and secret rotation.

### Phase 3 — Durable ingestion and authorized retrieval

**Depends on:** phases 1–2 and D2–D4/D6.

- Implement tenant-scoped source inventory, upload/import authorization, type/size checks, quarantine/malware policy, provenance, crawl policy/robots, metadata and access classification. Preserve local crawling and Markdown import.
- Build S3 -> EventBridge -> SQS -> worker flow with durable job state, content/version idempotency keys, lease ownership/fencing, visibility extension, bounded retries/backoff, DLQ and operator replay. Duplicate events, worker crash, out-of-order updates and repeated uploads must not incorrectly activate or overwrite a newer version.
- Integrate the Managed KB managed connector and sync lifecycle, map only validated metadata, observe failures/skipped formats, and verify tenant filters and ACL behavior in the chosen account. Treat managed ingestion/chunking as service-owned; do not also assume application-generated embeddings can be directly inserted into it.
- Build and evaluate the second explicit BM25/exact-match index/channel as decided under D3. Ensure analyzer configuration preserves identifier fields, metadata/ACL filters match the dense path, document deletes and ACL changes propagate, and no content reaches fusion/reranking until authorization is proven.
- Create immutable candidate releases with manifest (source checksums, parser/chunker, embedding/index/reranker, lexical analyzer/mapping, fusion, and policy versions). Promote the dense and lexical indexes as one consistent release. If Managed KB cannot isolate candidates or atomically switch, use separate KB resources and an application-owned conditional active pointer, or select an approved alternative under D3. Validate per-channel readiness, hybrid recall/quality and authorized retrieval before promotion; retain the prior consistent release for rollback. Define cache invalidation and consistent per-request version pinning.
- Implement deletion/revocation propagation across source objects, metadata, managed index, caches, replicas and backups per approved policy, with status/audit and verification. Include restore and orphan reconciliation.

**Exit:** authorization and quality tests pass for actual retrieval, including stale/revoked ACLs; failure-injection demonstrates retry, DLQ, candidate promotion, rollback and deletion without cross-tenant exposure.

### Phase 4 — Production answer pipeline

**Depends on:** phases 2–3, D3 and D8.

- Implement Bedrock generation, approved routing/fallback, guardrail integrations and independent claim/evidence/citation validation behind the ports; use bounded context and explicit token/deadline budgets. Benchmark dense, lexical and fused candidate sets, fusion, reranker and provider-specific evidence thresholds; don't transplant local similarity thresholds.
- Make authorization precede cache reads and all provider calls. Cache only policy-permitted validated results; key by tenant, effective authorization scope/policy revision, index, model, prompt, guardrail and retrieval/reranker versions. On revocation/version change invalidate or bypass stale entries. Default production web search off until D4 approves provider, consent, redaction, budgets and source labeling.
- Add distributed per-user/tenant quotas and generation leases, overload responses, retry/circuit-breaker policy, cancellation and finally-based release. Define behavior if Redis, policy, retrieval, guardrail or model is unavailable; security-critical failures deny, capacity failures return typed overload/unavailable responses.
- Deliver production SSE and non-stream endpoints, UI integration and evaluation adapter; verify the D8 policy before exposing any answer text.

**Exit:** end-to-end tests prove permitted evidence only, correct safe failures, cache isolation/revocation, guardrail handling, bounded retries, streaming terminal events and cleanup across failure/disconnect.

### Phase 5 — Operations, supply chain and recovery

**Depends on:** phases 2–4.

- Deploy multi-AZ chat and workers, Redis, queue/DLQ and supporting services; set resource bounds, autoscaling and downstream capacity limits. Configure dependency-aware readiness without turning transient overload into destructive restart loops.
- Add structured logs, metrics and OpenTelemetry traces for auth, each retrieval channel, fusion, reranking, safety, generation, cache, queue and streaming. Measure per-stage latency/errors, candidate counts/overlap, exact-match/fusion/reranker evaluation samples, index lag/version parity, authorization denials, quota use, cache hit/miss, TTFT, tokens and cost. Record request/tenant-safe identifiers and release versions, never raw prompts, source text, answers or secrets by default. Configure access/retention, dashboards, synthetic probes and actionable alerts.
- Set up encrypted/versioned backups, retention, deletion and restoration for source data and metadata. Define RPO/RTO, incident ownership and runbooks for provider outages, DLQ, stale index, credential rotation and region loss. Execute restore, index rollback and disaster-recovery drills; a managed KB may need rebuilding rather than snapshot restore.
- Build immutable release images with pinned dependencies/base digests, vulnerability and license policy, SBOM, signatures/attestations, migrations and rollback gates. Use staging, canary and an automatically enforced rollback decision based on measured health and quality.

**Exit:** staging drills demonstrate recovery against approved RPO/RTO; dashboards, alerts, on-call, rollback and verified release artifacts are available.

### Phase 6 — Quality, capacity and launch

**Depends on:** phases 2–5 and approved D7.

- Implement the dataset, annotation protocol, per-channel retrieval/ranking metrics, answer/safety/abstention metrics and online evaluation process in section 5.5. Record dataset hash and all model/index/lexical mapping/fusion/reranker/policy/evaluator versions; calibrate automated judges against humans and report confidence intervals.
- Make approved per-slice thresholds blocking for retrieval quality, exact-match, fusion/reranker lift, supported claims, citations, abstention, unauthorized retrieval/disclosure, safety, latency, cost and regression; test the gate itself with deliberately failing fixtures. Zero unauthorized disclosures is a release invariant, not a statistical guarantee.
- Run unit, adapter contract, integration, browser E2E, API/schema, migration, load, soak, security, streaming disconnect and dependency-failure suites in staging. Measure p50/p95/p99, TTFT, completion, concurrency, retries, costs, quota reservations and cache cold/warm states.
- Convert 10,000 sessions into measured active requests, retrieval rate, concurrent streams, token demand and burst headroom. Verify account/region/model quotas, residency and cost budgets; ramp 10%, 25%, 50%, 75%, 100% and 125% of approved peak and test backpressure and failover. Record whether each SLO is met; don't infer it from session count.
- Release via shadow, internal tenant, small canary and controlled expansion. Require security, product and operations sign-off and rollback triggers before public access.

**Exit:** all mandatory gates, capacity evidence, recovery exercises, cost and on-call approvals pass; otherwise remain private and non-production.

### Phase 7 — Continuous operation

**Depends on:** launch approval.

- Re-evaluate every model, prompt, embedding, index, reranker and policy change; monitor drift, authorization failures, spend and model/connector changes.
- Run periodic access reviews, adversarial and restore drills, vulnerability remediation, deletion audits and quota/capacity reviews. Document owners and release/incident evidence.

**Exit:** ongoing operational cadence and accountable owners; this phase does not mark safety or quality as permanently solved.

## 7. Verification and release evidence

| Gate | Required evidence |
|---|---|
| Local compatibility | `make lint`, `make test`; local startup and a representative local eval with model/index versions. |
| Isolation | No cloud credentials/network required locally; no local/shared-key/fail-open fallback in production; composition and dependency lifecycle tests. |
| Authorization | Token validation, tenant/collection/document isolation, source and conversation IDOR tests, revocation/cache propagation and denied-provider-call assertions. |
| Ingestion and data | Duplicate delivery, crash/lease expiry, poison message/DLQ, version races, atomic promotion/rollback, deletion and restore evidence. |
| Hybrid retrieval and ranking | Dense, BM25/exact and fused ablations; per-slice Recall@K/Precision@K/MRR/MAP/NDCG; exact-ID recall; fusion/reranker uplift; ACL parity and index-version consistency. |
| Answer and stream | Human-adjudicated factual correctness and claim support; citation precision/recall/completeness; abstention and calibration; safety and false-block tests; malformed events, output policy, disconnect/cancellation and exactly one terminal event. |
| Infrastructure | IaC/policy review, private network, secrets rotation, vulnerability/SBOM/signature checks, staging smoke, backup and DR drills. |
| Performance and quality | Approved per-segment golden-set results with confidence intervals and threshold-gate failure tests; measured peak/burst, token quotas, per-stage latency, SLO/error budget and cost evidence. |

Record exact commands, environment, commit/image digest, date, dataset/index/model versions, thresholds, result and owner in each release record. Never publish unmeasured performance or claim that a unit test proves production isolation at scale.

## 8. Risks and rollout controls

| Risk | Control / decision |
|---|---|
| Managed KB cannot enforce required ACLs or version switching. | D3 capability/security proof first; fail closed; use separate resources or an explicitly approved alternate retrieval design. |
| Managed KB built-in hybrid search does not meet explicit BM25/exact-identifier requirements, or dual indexes drift. | Run exact-match benchmarks; maintain a separate lexical channel only with versioned dual-index ingestion, ACL parity, lag monitoring and atomic promotion/rollback. |
| Reranker reorders plausible but unsupported passages or increases latency/cost. | Measure gains on locked per-query-class sets; bound candidate depth, latency budget, and cost; use ablations and rollback to the prior pipeline. |
| Guardrails are mistaken for hallucination prevention. | Combine input/output safety, authorization, grounded evidence selection, claim-level validation, abstention, human adjudication and online sampling; communicate residual uncertainty. |
| Streaming leaks text before full-answer validation. | D8 defines provisional versus buffered semantics; validate before release where confidentiality/grounding requires it. |
| Scores and model behavior change across providers. | Version and benchmark provider-specific policies and regression datasets; no blind threshold reuse. |
| Cache or index outlives access changes. | Authorization before every hit, versioned scope, invalidation and revocation tests; deny if freshness cannot be established. |
| Local refactor changes API or requires AWS. | Local-first compatibility suite and explicit composition tests; retain existing endpoints locally. |
| 10,000 sessions exceed actual inference capacity or budget. | Traffic model, quotas, measured load and cost gates, distributed backpressure and staged launch. |
| User data exits through web search, inference or logs. | Explicit policy/consent and residency decisions, minimization, encryption, access control and retention; web fallback off by default in production. |

## 9. Definition of done

This plan is a production-oriented implementation blueprint, **not confirmation that this application is production-ready**. Production is ready only when the approved identity and document boundaries, durable ingestion/versioned hybrid retrieval, measured reranking and exact-match quality, safety and citation controls, environment isolation, distribution/capacity, observability, recovery, release supply chain, and quality/load gates above have independently passed in the target environment. Hybrid retrieval, reranking and guardrails can improve measured quality and reduce risk; they cannot guarantee high accuracy or eliminate hallucinations. Until the evidence exists, the current application remains a local-first demonstration or trusted private deployment, not a public multi-tenant production service.

## 10. References

- [Amazon Bedrock Knowledge Bases: querying and retrieval](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve.html) — current managed retrieval behavior, hybrid search and reranking options; verify the selected model, connector, region and request configuration during implementation.
- [Amazon Bedrock Knowledge Bases overview](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html) — managed versus customer-managed responsibilities.
- [Amazon Bedrock Managed Knowledge Base retrieval](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-how-retrieval.html) — verify current API and filtering details before implementation.

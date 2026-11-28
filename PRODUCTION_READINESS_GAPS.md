# Production Readiness Gaps

## 1. Assessment summary

**Current status: suitable for local demonstrations and trusted private use; not ready for an internet-facing or multi-user production deployment.**

The application has several production-oriented local capabilities: non-root containers, loopback Docker bindings, shared-key authentication, request IDs, process-local rate limiting and generation limits, readiness checks, index checksums, tests, linting, dependency auditing, and CodeQL scanning. The latest implementation also adds validated environment settings and an application factory with injectable service/guardrail dependencies. This is only a local composition foundation: staging and production deliberately fail closed, and no production adapters or deployment have been implemented.

The main blockers remain identity and authorization, complete environment-specific adapters, dense-plus-BM25 retrieval and reranking, distributed operational controls, durable ingestion and storage, production observability, security hardening around external access, resilience guarantees, and evidence-based quality gates.

## 2. What is already implemented

| Area | Existing implementation |
|---|---|
| Configuration and composition | Frozen validated settings, FastAPI app factory, injected local service/guardrail factories, and test fakes; staging/production app creation is rejected |
| Local RAG | Sentence-transformer embeddings, FAISS retrieval, and local Ollama generation |
| Retrieval quality | Dense FAISS retrieval and local thresholds; no BM25/exact-match branch, rank fusion, or reranker |
| Grounding | Retrieval thresholds, source minimums, prompt source boundaries, and abstention |
| API authentication | Shared bearer-key validation on chat endpoints |
| API capacity | Per-IP in-process rate limiting and bounded concurrent generation |
| Readiness | API key, Ollama reachability, index loading, and model availability checks |
| Index integrity | Stable chunk IDs, manifest metadata, and SHA-256 artifact checksums |
| Streaming | Ollama NDJSON token streaming with a non-streaming fallback |
| Optional controls | Scope guardrail, ambiguity clarification, web-search fallback, and response cache |
| Containers | Docker Compose, non-root application containers, dropped Linux capabilities, and loopback port bindings |
| Quality automation | pytest, Ruff, GitHub Actions, pip-audit, container build, and CodeQL |
| Evaluation | JSONL answer-quality dataset, retrieval/citation metrics, abstention metrics, latency output, and optional thresholds |

## 3. Production gap matrix

| Priority | Gap | Why it blocks production | Recommended control |
|---|---|---|---|
| Critical | No production adapters or complete environment-specific composition | The application factory intentionally rejects staging/production; the RAG internals still use local implementations | Extract and contract-test required ports, then compose only approved identity, retrieval, generation, storage, safety, and distributed-control adapters per environment |
| Critical | No end-user identity or document authorization | Anyone possessing the shared key is trusted as the same principal | Add OIDC, per-user sessions, roles, and tenant/document ACLs |
| Critical | Shared API key is only a process credential | It cannot provide isolation, audit attribution, revocation per user, or least privilege | Replace or augment the key with authenticated API sessions and scoped service credentials |
| Critical | No TLS termination or secure public ingress | API traffic and bearer credentials may be exposed | Deploy behind authenticated HTTPS ingress and a trusted reverse proxy |
| Critical | Sensitive ingestion and retrieval lack tenant boundaries | A future multi-user deployment could cross user/document boundaries | Introduce tenant IDs, authorization checks at retrieval, and isolated storage |
| Critical | No durable ingestion workflow | Rebuild failures, retries, crashes, and concurrent updates lack restart-safe coordination | Add a queue, workers, idempotency keys, statuses, retries, and dead-letter handling |
| High | Process-local rate limiting and generation capacity | Limits differ across replicas and restart; a capacity semaphore is not cluster-wide | Use gateway or distributed limits and shared worker capacity |
| High | Process-local cache | Cache entries are lost on restart and not shared across replicas | Use Redis or a bounded external cache with invalidation/versioning |
| High | Limited durability and rollback | Index and article replacement can be interrupted and lack formal backup/restore drills | Define atomic promotion, snapshots, versioned indexes, retention, and rollback |
| High | Limited observability | Request logs omit operational correlation beyond request IDs and aggregate metrics are absent | Add structured logs, metrics, traces, dashboards, SLOs, and alerts |
| High | No hybrid retrieval, exact-match channel, or reranker | Dense-only retrieval can miss exact identifiers and no measured reranking improves candidate ordering | Implement dense + BM25/exact-identifier retrieval, rank fusion, reranking, and per-channel/fused quality gates |
| High | No isolated secrets manager | `.env` is local configuration and can be copied or mismanaged | Integrate a secret store and managed key rotation |
| High | Web search is unaudited and provider-dependent | Queries leave the machine and provider behavior/availability can change | Add consent, policy controls, provider allowlisting, timeouts, budgets, and audit policy |
| High | Guardrail is a topic filter, not security enforcement | It fails open and can be bypassed through paraphrase or injection | Do not use it as authorization; add server-side policy and input/output safeguards |
| High | Prompt-injection protection is heuristic | Retrieved text is marked untrusted but cannot guarantee resistance | Add isolated tool permissions, output validation, redaction, adversarial tests, and monitoring |
| High | Production quality gates are not demonstrated | The evaluation set is small and heuristic; thresholds are optional | Build a representative consented set and set blocking quality thresholds |
| Medium | No browser end-to-end testing | UI failures and streaming issues may escape unit tests | Add Playwright or equivalent smoke and workflow tests |
| Medium | No load or resilience testing | Capacity, tail latency, and retry behavior are unmeasured | Add load tests, chaos/failure tests, and capacity benchmarks |
| Medium | No formal data lifecycle policy | Deletion, retention, encryption, licensing, and consent are not defined | Create a records and retention policy with encrypted storage and deletion workflows |
| Medium | Model and dependency pinning are incomplete | Runtime behavior can change when models or packages are updated | Pin release artifacts, model digests, lock files, and upgrade procedures |
| Medium | No disaster-recovery runbook | Recovery targets and restore evidence are not established | Define RPO/RTO, tested restores, incident roles, and escalation |
| Medium | No public deployment architecture | Docker Compose is not a HA or managed deployment platform | Use a supported orchestration/platform design for the target environment |

## 4. Detailed gap analysis

### 4.1 Identity, authorization, and isolation

The API validates a shared credential in [runtime/app.py](runtime/app.py). The key is required for chat endpoints, but it does not represent a user or tenant.

There is no:

- sign-in or OIDC integration;
- per-user or per-role policy;
- tenant or collection ACL;
- authorization check before retrieval;
- document-level read access;
- audit attribution for a specific person;
- independent key revocation;
- separation between public data and restricted data.

**Required for production:** OIDC or corporate identity, short-lived sessions, server-side authorization middleware, tenant-aware retrieval filters, scoped service accounts, and immutable audit events.

### 4.2 Network and transport security

The Compose configuration binds application ports to loopback by default. This is safe for local use, but loopback is not a production ingress strategy.

There is no built-in:

- TLS certificate management;
- WAF or managed ingress;
- authenticated reverse proxy;
- CORS policy;
- request-size or upload policy for an expanded ingestion API;
- DDoS or gateway protection;
- private service networking outside Compose.

**Required for production:** terminate TLS at a trusted ingress, restrict internal ports, configure security headers, enforce upload/query limits, and deploy behind identity-aware access controls.

### 4.3 Shared bearer key and secrets

`API_KEY` is a shared secret used for chat access. A leak grants the bearer of the key chat access until the key is rotated.

The key is loaded from environment configuration. It is not stored in a secret manager, and there is no key version, scope, expiry, or audit trail.

**Required for production:** replace the shared key for user-facing traffic with short-lived identity tokens, or use the key only as a strictly scoped service credential in a secret manager with rotation.

### 4.4 Process-local rate limiting and capacity

Rate limits use an in-memory ordered dictionary in [runtime/app.py](runtime/app.py). The generation semaphore is also process-local.

Consequences:

- limits reset on process restart;
- replicas enforce independent quotas;
- IP values are assigned through the direct client view;
- a reverse proxy can require trusted forwarding configuration;
- local concurrency controls do not prevent cluster-wide overload.

**Required for production:** gateway limits, identity-aware quotas, distributed rate limiting, queue depth limits, and capacity sizing with backpressure.

### 4.5 Ingestion durability and consistency

The crawler and index build are synchronous shell and Python workflows. There is no persistent job ledger or worker queue.

The gaps include:

- no resumable crawl job state;
- no durable worker lease or retry schedule;
- no idempotency token for repeated builds;
- no ingestion status API for long-running jobs;
- no atomic deployment of the complete index;
- no formal stale-index or partial-update policy;
- no malware scanning or document-format validation;
- no OCR or image/diagram interpretation.

The crawler does enforce robots policy with fail-closed behavior, but an unavailable robots policy prevents crawling rather than providing a durable audit or review workflow.

**Required for production:** a durable queue and worker, crawl/index manifests, idempotent operations, signed or checksummed source records, resumable tasks, status tracking, dead-letter handling, and atomic index promotion.

### 4.6 Storage and backup

Data is written into local or mounted directories:

- article JSONL;
- raw HTML;
- FAISS and embedding artifacts;
- response cache memory.

There is no:

- database-backed document inventory;
- encrypted object storage;
- backup policy;
- retention or deletion workflow;
- restore test;
- index lifecycle policy;
- snapshot/rollback manifest promotion.

**Required for production:** versioned object storage, encryption at rest, backup and restore targets, retention classes, deletion handling, and approval gates for index replacement.

### 4.7 Data privacy and external providers

By default, the core data path is local. With web search enabled, queries leave the machine through DuckDuckGo in [runtime/web_search.py](runtime/web_search.py#L11).

The application does not maintain a formal privacy or provenance inventory for:

- source crawl terms;
- document consent;
- personal or regulated data;
- query retention;
- provider logs;
- cache contents;
- deletion requests.

**Required for production:** explicit consent and policy, provider terms review, query minimization, redaction, regional constraints, retention controls, and a documented model of which user data crosses which boundary.

### 4.8 Guardrails and prompt safety

The scope guardrail uses an LLM to classify input in [runtime/guardrail.py](runtime/guardrail.py). It fails open on classifier or provider errors.

Retrieved text is marked untrusted in the RAG prompt, and answers are resolved from retrieved sources, but prompt injection remains possible. The guardrail is not authorization.

Required controls include:

- server-side authorization independent of model output;
- structured output validation;
- strict tool permissions;
- adversarial prompt-injection tests;
- source and answer provenance;
- redaction and data-loss controls;
- monitoring for repeated rejection, leakage, or anomalous output.

### 4.9 Resilience and availability

The application has no formal dependency timeout policy across all stages, retries for Ollama, circuit breaking, or degraded-mode contract beyond UI fallback behavior.

The UI can fall back from streaming to `/chat`, but a provider outage can still prevent answer generation.

No high availability controls are provided for:

- Ollama;
- FAISS index availability;
- response cache;
- ingress;
- worker and API replicas;
- long-running generation;
- partial upgrades.

**Required for production:** dependency budgets, bounded retries with backoff and jitter, circuit breakers, provider or model fallback policy, replica health, graceful degradation, load shedding, and tested restart behavior.

### 4.10 Observability

The middleware adds a request ID and structured HTTP timing logs in [runtime/app.py](runtime/app.py). It does not collect a production metrics and tracing contract.

Missing telemetry includes:

- OpenTelemetry traces;
- retrieval latency and hit-rate distributions;
- citation success and abstention rates;
- Ollama queue and generation latency;
- web-search success and quota metrics;
- cache hit ratio;
- rate-limit and semaphore rejection metrics;
- model/index versions on response;
- alerting and dashboard definitions;
- centralized log retention and correlation;
- synthetic readiness probes.

**Required for production:** metrics, traces, business-level RAG telemetry, SLO dashboards, alerting, log access control, and privacy-safe event schemas.

### 4.11 Quality and evaluation

The evaluation runner measures:

- retrieval source recall;
- citation source recall;
- answer-term coverage;
- abstention precision and recall;
- outcome accuracy;
- latency.

These are useful heuristic checks. Gaps remain:

- no BM25/exact-identifier retrieval, dense/lexical rank fusion, or reranker implementation;
- no channel ablations or exact-identifier recall gate;
- no human-verified broad evaluation set;
- no faithfulness or hallucination judge accepted as a release gate;
- no per-domain, long-document, or paraphrase split;
- no adversarial prompt-injection set;
- no live non-synthetic quality benchmark;
- no cost or token budget metrics;
- no model-size hardware matrix;
- no automation evidence that evaluation thresholds block deployment;
- no statistical confidence or drift monitoring;
- no required per-slice Recall@K, Precision@K, MRR, MAP, NDCG, fusion/reranker uplift, or ACL-parity gate.

**Required for production:** a consented and sanitized golden set, source/answer provenance review, human adjudication, dense and BM25/exact-match channel metrics, rank-fusion and reranker ablations, retrieval and answer-quality thresholds, adversarial cases, confidence intervals, regression automation, and periodic re-evaluation. Retrieval should be measured per slice with at least Recall@K, Precision@K, MRR, MAP, NDCG, exact-identifier recall, unauthorized retrieval rate, and latency; answer evaluation should include citation precision/recall, supported-claim coverage, unsupported-claim rate, abstention quality, and human review. A judge model may support review but is not proof of truth or a replacement for human adjudication.

### 4.12 Testing and CI

The repository includes unit tests and CI for Python 3.10-3.12, lint, dependency audit, container build, and CodeQL. Missing production gates include:

- browser end-to-end tests;
- API contract/schema tests;
- streaming protocol tests under disconnect and timeout;
- FAISS migration/index compatibility tests;
- concurrent and multi-worker tests;
- load tests and latency SLO checks;
- container security image scanning;
- signed images and SBOM;
- deployment smoke tests;
- database/storage migration rollback tests;
- failure injection;
- evaluation thresholds as a deployment gate;
- settings validation, injected dependency, startup/shutdown, and fail-closed environment contract coverage for each production adapter.

**Required for production:** staged quality gates for unit, integration, end-to-end, load, security, evaluation, and deployment smoke checks.

### 4.13 Packaging and deployment

The Docker image is non-root, and Compose drops capabilities. It does not provide:

- image signing or SBOM;
- immutable pinned base-image digest;
- image vulnerability policy;
- Kubernetes or managed deployment manifests;
- secrets injection;
- autoscaling;
- rollout and rollback automation;
- migration gates;
- health/readiness deployment integration;
- resource requests/limits;
- pod disruption or multi-zone behavior;
- a staging/production composition root or production service adapters.

**Required for production:** a deployment target with immutable releases, supply-chain attestations, resource controls, rollout strategy, health checks, and rollback.

### 4.14 Environment-aware composition and dependency injection

The current code now has a frozen, validated settings object, a FastAPI application factory, and injection points for the RAG service and guardrail. Local factories construct the existing local stack; tests can inject fakes. The application rejects `staging` and `production` rather than silently selecting local providers. This is a safe foundation, not a production environment.

Remaining gaps:

- the main RAG service still combines retrieval, generation, cache, citation, and policy behavior rather than depending on independently replaceable ports;
- no production implementations exist for identity/authorization, retrieval, generation, durable storage/ingestion, distributed cache/capacity, or production guardrails/telemetry;
- production dependency lifecycle, startup/readiness checks, shutdown cleanup, and adapter contract tests are not established;
- the local shared key, FAISS/Ollama dependencies, process-local limits, and cache must not become production fallbacks.

**Required:** complete the ports-and-adapters refactor incrementally, preserve the local behavior behind local adapters, add explicit production composition only when its required adapters and settings are present, and test both successful local composition and fail-closed production behavior. Keep provider selection in composition roots rather than branching on environment throughout business logic.

### 4.15 Data and model lifecycle

The embedding model and answer model are configurable, but no complete lifecycle policy exists.

Risks include:

- rebuilding an index with a mismatched embedding model;
- mixing index versions across replicas;
- replacing the Ollama model without quality or capacity testing;
- no model checksum or signature;
- no deprecation policy;
- no hardware benchmark or fallback model;
- no documented licensing/provenance review.

**Required for production:** model registry or release manifest, index compatibility gates, pinned digests, hardware SLO tests, rollback models, licensing review, and usage/cost budgets.

## 5. Minimum production acceptance criteria

The application should not be called production-ready until it has:

1. End-user authentication and tenant/document authorization.
2. HTTPS ingress and private internal networking.
3. Distributed rate limits, quotas, queueing, and capacity controls.
4. A durable ingestion system with retries, status, idempotency, and atomic index promotion.
5. Versioned, encrypted, backed-up storage with tested restore and deletion procedures.
6. Secret-manager integration and credential rotation.
7. Structured metrics, logs, traces, dashboards, alert thresholds, and incident runbooks.
8. Prompt-injection and data-exfiltration threat tests.
9. A consented, representative evaluation set with blocking dense/BM25 retrieval, rank-fusion, reranker, answer-grounding, and safety thresholds.
10. Load, failover, concurrency, and streaming reliability tests.
11. Signed and scanned container releases with pinned dependencies and SBOMs.
12. Deployment rollout, rollback, backup, incident, and on-call procedures.
13. Environment-specific composition and adapter contract tests, with no silent local or fail-open fallback in staging/production.

## 6. Recommended implementation roadmap

### Phase 1: Security and trust boundary

- Retain the completed local composition foundation: validated settings, an application factory, injected local service/guardrail factories, and test fakes. Staging and production remain intentionally unavailable until production adapters exist.
- Finish extracting local retrieval, generation, cache, storage, authorization, and telemetry responsibilities behind explicit ports while preserving the local API behavior.
- Add OIDC or another supported identity provider.
- Move authorization to server-side middleware.
- Add tenant/document ACL checks before FAISS retrieval.
- Put TLS and gateway controls in front of the service.
- Remove user-facing use of the shared key.
- Add secret management and credential rotation.
- Define privacy and data-retention policies.

### Phase 2: Reliability and operations

- Replace process-local limits and cache with shared infrastructure.
- Add queue-based ingestion and isolated workers.
- Implement atomic index version promotion and rollback.
- Add metrics, tracing, central logs, dashboards, and alerts.
- Establish backup/restore and disaster-recovery procedures.
- Add service SLOs and capacity benchmarks.

### Phase 3: Quality and release gates

- Expand the evaluation dataset across domains and failure cases.
- Implement dense + BM25/exact-match retrieval, ranked-list fusion, and an independently evaluated reranker; gate channel and fused results using retrieval metrics and answer-support evaluation.
- Add human answer-faithfulness review.
- Add prompt-injection, leakage, and authorization tests.
- Add browser, load, streaming, concurrency, and failure tests.
- Make evaluation and security checks mandatory before release.

### Phase 4: Scale and deployment

- Select a supported production platform.
- Add autoscaling, resource limits, and multi-replica topology.
- Publish signed images and attestations.
- Implement deployment smoke checks and automated rollback.
- Add model lifecycle and cost governance.

## 7. Interim operating posture

Until the gaps above are closed, the app should be described as:

> A local-first RAG demonstration and trusted private self-hosted application. It is not suitable for public, shared, regulated, or high-availability deployments.

It may be operated privately when the operator:

- keeps ports bound to localhost or a controlled private network;
- uses the API key only with trusted users;
- has one authority over documents and answers;
- does not collect sensitive or regulated data;
- disables web search unless external query disclosure is accepted;
- backs up source material and index artifacts;
- monitors service and model failures;
- reviews output for the intended use case.

This operating posture reduces some risk, but it does not turn the application into a production-ready multi-user system.

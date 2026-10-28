# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Bearer-key protection for chat endpoints, per-process request/concurrency limits, readiness checks, and request IDs
- Versioned index manifests with stable chunk IDs and artifact checksums
- Robots.txt-aware crawling and an expanded heuristic evaluation harness
- Hardened Docker defaults, production-boundary documentation, and interview showcase guide
- Environment-driven branding and knowledge-base settings (`common/branding.py`, `.env.example`)
- Generic logo and icon, neutral sample corpus and `make sample`
- Configurable crawler URLs, URL segments and user agent
- `stop.sh`, Makefile, Dockerfile, docker-compose, CI workflow, tests and community files

### Changed
- Weak retrieval now abstains instead of falling back to ungrounded model knowledge
- Optional web search is disclosed as an external query path; Compose ports bind to localhost by default
- Real token streaming from Ollama; the final answer is sent before follow-up suggestions are computed
- Reasoning ("thinking") is disabled by default via `OLLAMA_THINK=false` for much faster first tokens
- The API loads its index at startup instead of on the first request
- Prompts, guardrail and clarifier are generic and built from the configured domain

### Removed
- Third-party branding, scraped content and logs from the repository

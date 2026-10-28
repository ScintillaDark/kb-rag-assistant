# Security Policy

## Supported versions

No tagged release has been published yet. Until then, the current `main` branch is the only supported version.

## Reporting a vulnerability

Please **do not** open a public issue. Use GitHub's private
[security advisory](https://github.com/ScintillaDark/kb-rag-assistant/security/advisories/new) form for this repository and include:

- a description of the issue and its impact
- steps to reproduce, or a proof of concept
- affected version or commit

You can expect an initial response within a few days.

## Deployment notes

This project is a local-first showcase with a shared bearer-key API control, not a complete user identity or authorization system. The API key is required for chat requests. Before exposing it beyond `localhost`:

- generate a unique, high-entropy `API_KEY`; do not reuse it across projects
- terminate TLS at a trusted reverse proxy and add end-user authentication/authorization for shared deployments
- keep `HOST_BIND_ADDRESS=127.0.0.1` unless you have network controls in place
- use a gateway/shared store for rate limiting when running multiple workers or replicas
- never commit `.env` files; they may contain endpoints or credentials
- review `WEB_SEARCH_ENABLED`: when enabled, queries are sent to the configured web search provider
- review crawler source and terms; robots rules are enforced and inaccessible policies fail closed
- treat the optional LLM scope classifier as a convenience filter, not an authorization boundary

# Security Policy

## Supported versions

Only the latest release on the `main` branch receives security fixes.

## Reporting a vulnerability

Please **do not** open a public issue. Use GitHub's private
[security advisory](../../security/advisories/new) form for this repository and include:

- a description of the issue and its impact
- steps to reproduce, or a proof of concept
- affected version or commit

You can expect an initial response within a few days.

## Deployment notes

This project is a local-first demo and ships **without authentication**. Before exposing it beyond `localhost`:

- put it behind a reverse proxy with authentication and TLS
- keep `API_HOST=127.0.0.1` unless you have network controls in place
- never commit `.env` files; they may contain endpoints or credentials
- review `WEB_SEARCH_ENABLED`: when enabled, user questions are sent to a web search provider
- respect the terms of service and `robots.txt` of any site you crawl

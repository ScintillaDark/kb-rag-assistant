# Contributing

Thanks for your interest in improving KnowledgeBase Assistant!

## Getting set up

```bash
git clone https://github.com/ScintillaDark/kb-rag-assistant.git
cd kb-rag-assistant
make install-dev
make sample
```

## Workflow

1. Open an issue (or comment on an existing one) before starting larger changes.
2. Create a branch from `main`: `git checkout -b feature/short-description`.
3. Keep changes focused; add or update tests in `tests/` and docs where behaviour changes.
4. Run `make lint` and `make test` before pushing.
5. Open a pull request using the template. CI must pass.

## Guidelines

- Keep the project **local-first**: no feature may send documents or questions to a third party by default.
- Anything specific to one knowledge base (names, URLs, topics, logos) belongs in `.env` / `common/branding.py`, never hard-coded.
- Do not commit scraped third-party content, indexes (`data/`), logs, or `.env` files.
- Use clear commit messages in the imperative mood (`Add streaming timeout setting`).

## Reporting bugs

Include your OS, Python version, Ollama model, the relevant part of `logs/api.log`, and steps to reproduce. For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

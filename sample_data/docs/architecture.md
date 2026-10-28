# Architecture

## Components
The system has four parts. The ingest scripts discover, download and clean documents. The indexer splits them into chunks, computes embeddings with a sentence-transformers model and stores them in a FAISS index. The runtime is a FastAPI service that retrieves passages, builds a prompt and streams the answer from Ollama. The user interface is a Streamlit chat application that shows the answer with citations.

## Request flow
A question first passes through an optional scope guardrail and an ambiguity check. The service embeds the question, searches the FAISS index and keeps the passages above the similarity threshold. If there is enough evidence, the passages are placed in the prompt and the answer is generated token by token. If evidence is weak, the assistant abstains unless optional web search returns sources. The response includes citations and may include suggested follow-up questions. Repeated questions are served from an in-process cache.

## Privacy
Documents, embeddings and local Ollama inference stay on your machine by default. Crawling accesses the configured documentation site; optional web search sends the user's query and search request to its provider.

## Extending
Because the branding and the subject area come from environment variables, the same code base can serve any documentation set. Swap the corpus, edit `.env`, rebuild the index and restart the services.

# Architecture

## Components
The system has four parts. The ingest scripts discover, download and clean documents. The indexer splits them into chunks, computes embeddings with a sentence-transformers model and stores them in a FAISS index. The runtime is a FastAPI service that retrieves passages, builds a prompt and streams the answer from Ollama. The user interface is a Streamlit chat application that shows the answer with citations.

## Request flow
A question first passes through an optional scope guardrail and an ambiguity check. The service embeds the question, searches the FAISS index and keeps the passages above the similarity threshold. If there is enough evidence, the passages are placed in the prompt and the answer is generated token by token. The response includes citations that link back to the source documents, and a short list of suggested follow-up questions. Repeated questions are served from an in-process cache.

## Privacy
Documents, embeddings and the language model all stay on your machine. The only optional network calls are the crawler used during indexing and the web search fallback, which is disabled by default.

## Extending
Because the branding and the subject area come from environment variables, the same code base can serve any documentation set. Swap the corpus, edit `.env`, rebuild the index and restart the services.

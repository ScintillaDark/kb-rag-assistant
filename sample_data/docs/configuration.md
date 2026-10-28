# Configuring KnowledgeBase Assistant

## Branding and domain
The application name, tagline, logo, suggested questions and subject area are controlled by environment variables in the `.env` file. Set `APP_NAME` to change the title shown in the browser and the chat window. Set `KB_DOMAIN` and `KB_TOPICS` to describe what your knowledge base covers; these values are used in the prompts and in the optional scope guardrail. Replace `assets/kb-logo.svg` and `assets/kb-icon.png`, or point `APP_LOGO_PATH` and `APP_ICON_PATH` at your own images.

## Retrieval settings
`RAG_TOP_K` controls how many passages are retrieved for every question. `RAG_SIMILARITY_THRESHOLD` is the minimum cosine similarity a passage needs to be used as evidence. Raising it makes the assistant more conservative; lowering it lets weaker matches through. `RAG_MIN_SOURCES` sets how many distinct documents must support an answer.

## Model settings
`OLLAMA_BASE_URL` points to the Ollama server and `OLLAMA_MODEL` selects the model. `OLLAMA_TIMEOUT` is the maximum time in seconds to wait for the model between tokens. Smaller models respond faster on machines without a GPU.

## Optional features
Set `GUARDRAIL_ENABLED=true` to reject questions that are outside the configured scope. Set `WEB_SEARCH_ENABLED=true` to fall back to a web search when the knowledge base has no relevant passage. Set `RAG_CLARIFICATION_ENABLED=false` to stop the assistant from asking clarifying questions for vague input.

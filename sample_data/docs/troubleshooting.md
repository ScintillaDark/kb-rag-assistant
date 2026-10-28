# Troubleshooting

## Answers are very slow
Generation speed depends on the model and the hardware. On a CPU-only machine a model with several billion parameters may produce only a few tokens per second. Choose a smaller model through `OLLAMA_MODEL`, close other heavy applications, or run Ollama on a machine with a GPU. The chat window streams the answer as it is generated, so you can start reading before the full response is ready.

## The assistant says it has not enough evidence
The retrieved passages scored below `RAG_SIMILARITY_THRESHOLD`, or fewer than `RAG_MIN_SOURCES` distinct documents matched. Lower the threshold slightly, rebuild the index with more content, or rephrase the question with more specific words.

## Cannot connect to Ollama
Check that the Ollama server is running with `ollama list`. Start it with `ollama serve` if needed, and make sure `OLLAMA_BASE_URL` matches its address. Confirm that the model named in `OLLAMA_MODEL` has been pulled.

## Python venv fails on Ubuntu or Debian
If creating a virtual environment fails with an ensurepip error, install the venv package with `sudo apt install python3-venv` and create the environment again.

## The API starts but the chat page is empty
Verify that the API responds at http://127.0.0.1:8000/health and that `RAG_API_URL` in `.env` points to it. Check `logs/api.log` and `logs/ui.log` for errors.

# Getting Started with KnowledgeBase Assistant

## Overview
KnowledgeBase Assistant is a local-first question answering system. It indexes a set of documents once, then answers questions by retrieving the most relevant passages and passing them to a language model that runs on your own machine through Ollama. By default, question-time inference is local. If optional web search is enabled, the search query is sent to the configured web-search provider.

## Requirements
You need Python 3.9 or newer, about 8 GB of free memory for a small model, and Ollama installed and running. A GPU is optional. Without a GPU, answers are generated on the CPU and may take from a few seconds to a few minutes depending on the model size.

## Quick start
1. Create a virtual environment and install the dependencies with `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and adjust the settings.
3. Build the sample index with `make sample`.
4. Pull a model, for example `ollama pull gemma4:latest`.
5. Start everything with `./start.sh` and open http://localhost:8501.

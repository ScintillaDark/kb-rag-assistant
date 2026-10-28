FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch keeps the image much smaller than the default CUDA build
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000 8501
CMD ["python", "-m", "uvicorn", "runtime.app:app", "--host", "0.0.0.0", "--port", "8000"]

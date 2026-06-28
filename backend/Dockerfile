# Backend Dockerfile — FastAPI + Groq pipeline.
FROM python:3.11-slim

WORKDIR /app

# System deps needed by sentence-transformers/torch and lxml/bs4 parsing.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=120
# Install CPU-only torch explicitly first — sentence-transformers' default
# resolution otherwise pulls the full CUDA-enabled torch build (500MB+ plus
# several large nvidia-* CUDA packages), which is both unnecessary (this
# container has no GPU) and prone to timing out on slower connections.
RUN pip install --no-cache-dir --retries 5 torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --retries 5 -r requirements.txt

COPY app ./app

# Pre-download the cross-encoder + embedding models at build time so the
# first real request isn't stuck waiting on a ~100MB download.
RUN python -c "from sentence_transformers import CrossEncoder, SentenceTransformer; \
    CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); \
    SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

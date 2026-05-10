FROM python:3.12-slim

WORKDIR /app

# Install system deps needed by some Python packages on ARM
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline/ ./pipeline/

# data/ is mounted at runtime — not baked into the image
VOLUME ["/app/data"]

CMD ["python", "-m", "pipeline.run"]

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Layered slowest-changing to fastest-changing, so an ordinary dependency change
# does not re-download the ML stack. torch alone is ~200MB; sentence-transformers
# pulls transformers, scikit-learn and scipy behind it.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements-ml.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements-ml.txt

COPY requirements.txt .
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

WORKDIR /app

# tesseract-ocr: reads scanned bills that have no text layer. Without it a
# photographed or faxed bill silently extracts to an empty string, which the
# prototype reported as a successful parse of zero line items.
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
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

# syntax=docker/dockerfile:1
FROM python:3.12-slim

# system deps: tini for signals, curl for debug, plus build essentials & common headers
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini curl git build-essential python3-dev pkg-config cmake cargo \
    libffi-dev libssl-dev \
    libxml2-dev libxslt1-dev \
    zlib1g-dev libjpeg-dev \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir -U pip setuptools wheel


ENV PYTHONUNBUFFERED=1 TZ=UTC
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy whole project (your folders + main.py + manager.py)
COPY . .

ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","-m","manager","run-bot"]
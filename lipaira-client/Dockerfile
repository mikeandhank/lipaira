FROM python:3.11-slim

WORKDIR /app

# WeasyPrint requires Cairo, Pango, and GDK-PixBuf for PDF rendering
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    flask \
    anthropic \
    httpx \
    pydantic \
    requests \
    psycopg2-binary \
    weasyprint \
    jinja2 \
    google-auth \
    google-auth-oauthlib \
    google-api-python-client \
    msal

COPY agent.py .
COPY history.py .
COPY skills/ ./skills/

RUN mkdir -p /app/data/documents

RUN useradd -m -u 1000 agent
RUN chown -R agent:agent /app
USER agent

EXPOSE 7000
CMD ["python", "agent.py"]

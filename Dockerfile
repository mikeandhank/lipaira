FROM python:3.11-slim

# Labels
LABEL maintainer="Lipaira <dev@lipaira.ai>"
LABEL version="0.1.0"
LABEL description="Lipaira AI Agent OS - Secure self-hosted AI agent runtime"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LIPAIRA_MODE=self-hosted
ENV PYTHONPATH=/opt/lipaira/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create lipaira user
RUN useradd -m -s /bin/bash lipaira

# Create directories
RUN mkdir -p /opt/lipaira/{app,data,logs,plugins,config}
WORKDIR /opt/lipaira/app

# Copy application
COPY .  /opt/lipaira/app/
COPY lipaira-providers/ /opt/lipaira/app/lipaira-providers/

# Create symlinks — Python can't import directories with hyphens
RUN ln -sf /opt/lipaira/app/lipaira-client /opt/lipaira/app/lipaira_client || true
RUN ln -sf /opt/lipaira/app/lipaira-providers /opt/lipaira/app/lipaira_providers || true

# Install Python dependencies
RUN pip install --no-cache-dir --break-system-packages \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    gunicorn==21.2.0 \
    psycopg2-binary==2.9.9 \
    redis==5.0.1 \
    requests==2.31.0 \
    python-jose==3.3.0 \
    passlib==1.7.4 \
    bcrypt==4.1.2 \
    cryptography==41.0.7 \
    stripe>=8.0.0 \
    pydantic==2.5.3 \
    python-multipart==0.0.6 \
    boto3==1.34.0 \
    docker==7.0.0 \
    httpx==0.27.0 \
    croniter==1.4.1 \
    google-api-python-client==2.137.0 \
    google-auth-oauthlib==1.2.0 \
    google-auth-httplib2==0.2.0 \
    msal==1.28.0 \
    pywebpush==1.14.0 \
    numpy==1.26.4 \
    gremlinpython==3.7.1
# Set ownership
RUN chown -R lipaira:lipaira /opt/lipaira

# Expose ports
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run migrations first, then start gunicorn
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "120", "server_full:app"]

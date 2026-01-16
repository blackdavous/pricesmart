FROM python:3.11

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    gcc \
    libxml2-dev \
    libxslt-dev \
    pkg-config \
    libpq-dev \
    cmake \
    git \
    rustc \
    cargo \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# --- RAM-SAFE INSTALLATION STRATEGY ---
# Install heavy libraries individually to prevent OOM
RUN pip install --no-cache-dir --prefer-binary numpy
RUN pip install --no-cache-dir --prefer-binary pandas
RUN pip install --no-cache-dir --prefer-binary scipy

# Install compilation-heavy libraries
RUN pip install --no-cache-dir --prefer-binary lxml brotli cryptography

# Install core framework
# Install core framework
RUN pip install --no-cache-dir --prefer-binary fastapi uvicorn[standard] sqlalchemy pydantic pydantic-settings structlog prometheus_client

# Install remaining dependencies explicitly
RUN pip install --no-cache-dir --prefer-binary \
    requests httpx \
    openai langchain langchain-openai langgraph \
    redis celery \
    python-dotenv \
    python-jose[cryptography] \
    beautifulsoup4

# Copy application code structure
COPY backend/app /app/app

# Set Python Path
ENV PYTHONPATH=/app

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

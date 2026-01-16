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
    postgresql-client \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Upgrade pip and install uv
RUN pip install --no-cache-dir --upgrade pip uv

# Create virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install requirements into venv
RUN uv pip install --no-cache -r requirements.txt

# Copy application code structure
COPY backend/app /app/app

# Set Python Path
ENV PYTHONPATH=/app

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

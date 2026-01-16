FROM python:3.11

WORKDIR /app

# Copy requirements
COPY requirements.txt .

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
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install uv
RUN pip install --no-cache-dir --upgrade pip uv

# Create virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install requirements into venv
RUN uv pip install --no-cache -r requirements.txt

# Copy application code
COPY frontend /app/frontend
COPY backend /app/backend

# Set Python Path to include backend
ENV PYTHONPATH=/app

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit
CMD ["streamlit", "run", "frontend/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]

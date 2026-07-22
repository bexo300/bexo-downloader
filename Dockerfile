#
# File 4: Dockerfile
dockerfile = '''# Bexo Downloader - Production Dockerfile
# Multi-stage build for optimal image size

# ═══════════════════════════════════════════════════════════
# Stage 1: Builder
# ═══════════════════════════════════════════════════════════
FROM python:3.12-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ═══════════════════════════════════════════════════════════
# Stage 2: Production
# ═══════════════════════════════════════════════════════════
FROM python:3.12-slim-bookworm AS production

LABEL maintainer="Bexo Team"
LABEL description="Bexo Downloader - Professional Media Download Bot"
LABEL version="1.0.0"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r bexo && useradd -r -g bexo -m -s /bin/bash bexo

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p bot/downloads bot/logs bot/cache bot/database && \
    chown -R bexo:bexo /app

# Copy application code
COPY --chown=bexo:bexo . .

# Switch to non-root user
USER bexo

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the bot
CMD ["python", "main.py"]
'''

with open("/mnt/agents/output/bexo_downloader/Dockerfile", "w", encoding="utf-8") as f:
    f.write(dockerfile)

print("✅ Dockerfile created")

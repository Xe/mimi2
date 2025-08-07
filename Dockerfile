# Dockerfile for mimi2 - AI Customer Support Agent
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Create non-root user
RUN groupadd -r mimi2 && useradd -r -g mimi2 mimi2

# Set working directory
WORKDIR /app

# Copy dependency files
COPY --chown=mimi2:mimi2 pyproject.toml uv.lock ./

# Install dependencies with fallback to pip
RUN uv sync --frozen --no-cache || \
    (pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org \
     aiosqlite==0.21.0 \
     discord-py==2.5.2 \
     duckdb==1.3.2 \
     lancedb==0.24.2 \
     ollama==0.5.2 \
     openai==1.99.1 \
     pandas==2.3.1 \
     pip==25.2 \
     pyarrow==21.0.0 \
     python-dotenv==1.1.1 \
     uuid6==2025.0.1)

# Copy application code
COPY --chown=mimi2:mimi2 . .

# Make sure the virtual environment is in PATH (or system packages if using pip)
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER mimi2

# Expose port if needed (for future web interface)
EXPOSE 8080

# Set default command
CMD ["python", "main.py"]
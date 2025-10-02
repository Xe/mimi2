# Stage 1: Builder
# This stage installs dependencies into a virtual environment.
FROM python:3.13-slim as builder

# Install uv, the package manager used by this project
RUN pip install uv

# Set up a virtual environment in /opt/venv
ENV VIRTUAL_ENV=/opt/venv
RUN uv venv $VIRTUAL_ENV

# Activate the virtual environment for subsequent commands
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy the dependency files
WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-cache

# Stage 2: Runner
# This stage copies the application code and the virtual environment.
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the application code
COPY . .

# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Set the default command to run the command-line interface
# The user can override this to run the Discord bot, e.g., by running:
# docker run <image_name> python discord_bot.py
CMD ["python", "main.py"]

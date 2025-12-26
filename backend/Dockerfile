# Backend Dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY *.py ./
COPY routers/ ./routers/

# Create charts directory
RUN mkdir -p charts

# Install dependencies
RUN uv sync --locked

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

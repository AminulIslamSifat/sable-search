FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
COPY app/ ./app/
COPY server.py ./
COPY config.yaml ./

# Install dependencies
RUN uv pip install --system -e .

EXPOSE 8080

CMD ["python", "server.py"]

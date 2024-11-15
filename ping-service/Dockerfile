FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install build-essential -y

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --compile-bytecode

# Copy the project into the image
ADD . /app

# Sync the project
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --compile-bytecode


FROM python:3.13-slim

COPY --from=builder /app/.venv /app/.venv

CMD ["/app/.venv/bin/uvicorn", "ping_thing.main:app", "--host", "0.0.0.0", "--port", "8080"]

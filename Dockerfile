# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY catalog ./catalog
COPY config ./config

RUN uv sync --extra telethon --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 1000 garimpo && chown -R garimpo:garimpo /app
USER garimpo

VOLUME ["/app/data"]

HEALTHCHECK --interval=5m --timeout=30s --retries=3 \
  CMD garimpo doctor --quick -c /app/config/config.yaml || exit 1

ENTRYPOINT ["garimpo"]
CMD ["run"]

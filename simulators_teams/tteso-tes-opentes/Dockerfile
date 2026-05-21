FROM python:3.12.11-slim

LABEL maintainer="GREI-UFC"
LABEL description="PADE environment for the OpenTES integration workspace."

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:${PATH}"
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /uvx /bin/

WORKDIR /app
COPY . /app

RUN uv sync --frozen

EXPOSE 3000/tcp
EXPOSE 8000/tcp
EXPOSE 8001/tcp

CMD ["sleep", "infinity"]

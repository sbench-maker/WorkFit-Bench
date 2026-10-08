FROM python:3.12.7-slim-bookworm
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv==0.4.20 && uv sync --frozen --no-dev
COPY rosterly rosterly
CMD ["uv", "run", "uvicorn", "rosterly.main:create_app", "--factory", "--host", "0.0.0.0"]

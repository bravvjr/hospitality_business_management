# Backend image (ADR-001: Python 3.14; ADR-003 container boundaries).
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
# Wheels-only: dependencies are pinned to versions with cp314 wheels, so pip
# never compiles from source. If a wheel is ever missing, the build fails fast
# with a clear error instead of hanging on a Rust/C compile.
RUN pip install --upgrade pip \
    && pip install --only-binary=:all: -r requirements.txt

COPY . .

RUN chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

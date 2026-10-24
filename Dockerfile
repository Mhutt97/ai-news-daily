FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml requirements.txt main.py ./
COPY src/ ./src/
RUN mkdir -p /app/digests

ENTRYPOINT ["python", "main.py"]

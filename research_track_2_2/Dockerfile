FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN useradd --create-home --uid 10001 experiment && mkdir -p /app/data/raw /app/results && chown -R experiment:experiment /app
USER 10001:10001
CMD ["python", "-m", "src.cli", "evaluate", "--dry-run"]

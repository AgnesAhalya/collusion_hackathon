FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN useradd --create-home --uid 10001 experiment && mkdir -p /app/data/labels /app/data/monitor_inputs /app/results && chown -R experiment:experiment /app
# Dependencies needed by the actual LTB runner mounted read-only at runtime.
RUN pip install --no-cache-dir python-dotenv==1.2.4 requests==2.34.2 aiohttp==3.14.5 openai==3.37.0 tqdm==4.70.1
USER 10001:10001
CMD ["python", "-m", "src.real_cli", "preflight"]

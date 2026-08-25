FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Copy browser transaction script and loop wrapper
COPY browser_transaction.py .
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh

# Environment variables with defaults
ENV TARGET_URL="https://google.com"
ENV TEST_TYPE="page"
ENV TEST_INTERVAL_SECONDS="300"
ENV METRICS_DIR="/metrics"

CMD ["./entrypoint.sh"]

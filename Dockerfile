FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY values.yaml .
COPY unichain_v4_pools.json .

CMD ["python", "-m", "src.main"]

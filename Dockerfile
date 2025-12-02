FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY values_local.yaml .
COPY values_remote.yaml .

CMD ["python", "-m", "src.main"]

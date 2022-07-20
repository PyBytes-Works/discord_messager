FROM python:3.10-slim

RUN apt-get update && \
    apt-get -y install libpq-dev gcc

WORKDIR /app

COPY requirements.txt .

RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir --upgrade -r requirements.txt && \
    python3 -m pip uninstall -y trio

COPY . .

CMD ["python", "main.py"]

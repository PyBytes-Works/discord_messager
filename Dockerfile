FROM python:3.9-slim

WORKDIR /app

ADD requirements.txt .

RUN apt-get update && \
    apt-get -y install libpq-dev gcc && \
    pip install psycopg2 && \
    python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt

ADD . .

CMD ["python", "main.py"]

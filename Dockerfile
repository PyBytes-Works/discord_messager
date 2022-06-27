FROM python:3.10-slim

RUN apt-get update && \
    apt-get -y install libpq-dev gcc

WORKDIR /app

ADD requirements.txt .

RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir --upgrade -r requirements.txt

ADD . .

CMD ["python", "main.py"]

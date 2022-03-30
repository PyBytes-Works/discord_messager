FROM python:3.9-slim

EXPOSE 6379

WORKDIR /app

ADD requirements.txt .

RUN python3 -m pip install --no-cache-dir --upgrade pip \
  && python3 -m pip install --no-cache-dir  \
    -r requirements.txt

ADD . .

CMD ["python", "main.py"]

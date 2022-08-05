FROM deskent/deskent:python_mailer-slim-3.10

WORKDIR /app

COPY requirements.txt .

RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

CMD ["python", "main.py"]

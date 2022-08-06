FROM deskent/deskent:python3.10-slim-psycopg2

WORKDIR /app

COPY requirements.txt .

RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]

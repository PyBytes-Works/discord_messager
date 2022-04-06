FROM python:3.9-slim

RUN echo "vm.overcommit_memory = 1" >> /etc/sysctl.conf

EXPOSE 6379

WORKDIR /app

ADD requirements.txt .

RUN python3 -m pip install --no-cache-dir --upgrade pip \
  && python3 -m pip install --no-cache-dir  \
    -r requirements.txt

ADD . .

CMD ["python", "main.py"]

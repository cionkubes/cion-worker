FROM python:3.6-alpine

WORKDIR /opt/worker

HEALTHCHECK --timeout=5s --retries=3 --start-period=30s CMD python healthcheck.py http://localhost:5000

RUN apk --no-cache add git

COPY requirements.txt .
RUN pip install -r requirements.txt --src /lib

COPY src/monkey_patch.py .
COPY src/healthcheck.py .
COPY src/configuration configuration
COPY src/worker.py .

CMD ["python", "worker.py"]

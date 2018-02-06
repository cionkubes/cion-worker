FROM python:3.6-alpine

WORKDIR /opt/worker

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/worker.py .
COPY src/monkey_patch.py .
COPY src/configuration configuration

CMD ["python", "worker.py"]
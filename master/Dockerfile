FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir mosaik==3.5

COPY ./scenario.py .
COPY ./monitor_sim.py .

CMD ["python3", "scenario.py"]

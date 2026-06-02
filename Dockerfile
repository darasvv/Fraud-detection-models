FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

COPY bot/ ./bot/
COPY ensemble_my_models.pkl .
COPY .env .

ENV PYTHONPATH=/app

CMD ["python", "tranbot.py"]
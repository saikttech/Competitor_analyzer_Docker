FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 🔍 ОТЛАДКА: Печатаем список пакетов, чтобы убедиться, что uvicorn и celery установились
RUN echo "=== ПРОВЕРКА УСТАНОВЛЕННЫХ ПАКЕТОВ ===" && pip list

COPY . .

RUN mkdir -p reports

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
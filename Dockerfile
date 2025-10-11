# Этап сборки
FROM python:3.10-slim as builder

# Установка необходимых системных библиотек
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Рабочая директория
WORKDIR /app

# Копируем requirements
COPY requirements.txt .

# Установка Python-зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Финальный этап
FROM python:3.10-slim

# Копируем виртуальное окружение из builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Рабочая директория
WORKDIR /app

# Копируем все необходимые файлы
COPY qwenChatBdGaven.py .
COPY qwenGmail.py .
COPY chroma_db .
COPY templates .

COPY railway.yml .
COPY vector_serch.py .
COPY requirements.txt .
COPY qwenparser.py .

# Команда запуска
CMD ["gunicorn", "qwenChatWeb:app", "-w", "1", "-k", "gevent", "--worker-connections", "100", "--timeout", "60", "-b", "0.0.0.0:5000"]
#CMD ["python", "qwenChatWeb.py"]
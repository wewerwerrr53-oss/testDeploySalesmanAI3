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

# Копируем всё приложение
COPY . .

# Команда запуска
CMD ["gunicorn", "app:app", "-w", "2", "-k", "gevent", "--worker-connections", "1000", "--timeout", "60", "-b", "0.0.0.0:5000"]



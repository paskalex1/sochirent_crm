FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

EXPOSE 8000

# По умолчанию команда переопределяется в docker-compose (runserver для разработки).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]


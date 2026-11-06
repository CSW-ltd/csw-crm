FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN pip install pipenv==2024.4.0
COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY . .
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000
# Migratsiyalarni qo'llab, keyin serverni ishga tushiradi
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:asgi_app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]

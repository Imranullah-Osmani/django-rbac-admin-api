FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py makemigrations accounts organizations audits && python manage.py migrate && python manage.py shell -c \"from config.bootstrap import ensure_system_roles, ensure_default_superuser; ensure_system_roles(); ensure_default_superuser()\" && python manage.py runserver 0.0.0.0:8000"]

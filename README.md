# PROJECT MARSLIB

A Flask-based school library management system with Gramedia catalog integration.

## Features

- Book catalog management
- Gramedia catalog sync
- Admin dashboard with logs
- Staff setup and authentication
- File upload support

## Tech Stack

- Python / Flask
- Flask-SQLAlchemy (SQLite)
- Gunicorn (production)
- HTML / CSS / JavaScript

## Deploy to Microsoft Azure App Service

This app is ready for an Azure App Service running Python 3.12 on Linux. Azure uses the `Procfile` to start Gunicorn, and the `/healthz` endpoint can be used for health checks.

Configure these App Service application settings before the first production start:

- `FLASK_SECRET_KEY`: a long random value that remains unchanged between deployments
- `DATABASE_URL`: preferably an Azure Database for PostgreSQL Flexible Server URL, for example `postgresql://user:password@server.postgres.database.azure.com:5432/library?sslmode=require`
- `FORCE_HTTPS`: `1`

When `DATABASE_URL` is not set, the app uses SQLite. On Azure, that database and uploaded identity files are stored under `/home/site/data` so they survive normal deployments. SQLite is suitable for a single-instance trial only; PostgreSQL should be used for production or scaled deployments.

### Azure CLI deployment

From this project directory:

```powershell
az login
az webapp up --name <unique-app-name> --resource-group <resource-group> --runtime "PYTHON:3.12" --sku B1
az webapp config appsettings set --resource-group <resource-group> --name <unique-app-name> --settings FLASK_SECRET_KEY="<random-value>" DATABASE_URL="<postgres-url>" FORCE_HTTPS=1
```

If the App Service does not pick up the `Procfile`, set its startup command to:

```text
gunicorn --bind=0.0.0.0:$PORT --timeout 600 wsgi:app
```

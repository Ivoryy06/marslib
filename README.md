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

## Setup

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
flask run
```

## Deployment

Uses `Procfile` for platforms like Render or Heroku:

```
web: gunicorn wsgi:app --bind 0.0.0.0:$PORT
```

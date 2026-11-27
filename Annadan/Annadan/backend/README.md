# Annadan API

FastAPI + SQLAlchemy backend for the Annadan static frontend. The root [`README.md`](../README.md) contains the full Vercel/Render/PostgreSQL deployment procedure and provider configuration.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set SECRET_KEY in .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive API schema: `http://127.0.0.1:8000/docs`. Liveness: `/health`. Database readiness: `/ready`.

Create the first admin (CLI only):

```bash
python -m app.scripts.create_admin
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## API groups

All application endpoints are under `/api/v1`: `auth`, `donations`, `requests`, `users`, `impact`, `admin`, `uploads`, and `payments`. Auth includes register/login, email OTP, optional Twilio phone verification and email-code password reset. Requests include participant-only tracking and delivery-partner location updates. Admin includes safety review and account controls. Payments are optional voluntary platform contributions through Razorpay.

## Production behavior

Production runs Alembic migrations before Uvicorn. Set `ENVIRONMENT=production`, a generated `SECRET_KEY`, a PostgreSQL `DATABASE_URL`, exact frontend origins in `CORS_ORIGINS`, and the secrets for every provider you enable. Do not use the development OTP setting or commit `.env`.

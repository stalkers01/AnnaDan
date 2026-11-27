# Annadan — live food donation platform

Annadan is a static HTML/CSS/JavaScript frontend connected to a FastAPI backend. The project is prepared for **separate deployment**: Vercel hosts the frontend, Render runs the API, and Render PostgreSQL stores application data. The existing visual theme and page layouts are retained.

## What is included

- Donor, receiver, delivery-partner, and administrator roles with protected API operations.
- JWT sign-in, hashed passwords, email OTP verification, optional phone OTP through Twilio Verify, and email-code password reset.
- Food donations, receiver requests, donor approval/rejection, atomic quantity reservation, delivery claiming, handover status and activity history.
- Food image upload to Cloudinary (JPEG/PNG/WebP, 5 MB limit).
- Optional donation pickup/receiver coordinates and live delivery-partner location sharing. The map uses Leaflet + OpenStreetMap by default; an optional Google Maps browser key can enable Google Maps.
- Email through Resend and SMS through Twilio, respecting account notification preferences.
- Admin food-safety checklist review queue. This is an operational review workflow, **not** laboratory testing or official food-safety certification.
- Optional Razorpay voluntary platform-support contributions. This does not charge recipients for donated food or delivery.
- Alembic database migrations, automated tests, health/readiness endpoints, Docker support, Vercel configuration and Render Blueprint.

Provider features are implemented as integrations but stay inactive until you configure your own provider credentials. No provider keys, payment credentials, or user data are included. Render compute/database resources are billed separately; Vercel static hosting may be available on its Hobby plan depending on its current terms.

## Local setup (Kali Linux)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Put the generated value into backend/.env as SECRET_KEY
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, from the project root (the folder containing `index.html`):

```bash
python3 -m http.server 5500
```

Open `http://127.0.0.1:5500`. API docs: `http://127.0.0.1:8000/docs`. The local config exposes OTP codes in development only; never enable that setting in production.

Create the initial administrator from the backend directory after the database migration: `python -m app.scripts.create_admin`. The CLI-created admin is marked verified; public signup cannot create an admin.

## Separate deployment: Vercel + Render + PostgreSQL

### 1. Push the project to GitHub

Create a private or public GitHub repository and push the complete project. Do not commit `.env`, database files, API secrets, or Razorpay/Twilio/Cloudinary credentials. The provided `.gitignore` excludes local environment and database files.

### 2. Create API + PostgreSQL on Render

1. In Render, choose **New → Blueprint**, connect this repository, and apply the root `render.yaml`.
2. The Blueprint creates the `annadan-api` web service and `annadan-db` PostgreSQL database in Singapore. It uses Render’s current small paid plans (`0.5c-512mb` web and `0.1c-256mb` Postgres), which are currently listed at about **US$7/month + US$6/month (US$13/month total)** before tax, bandwidth, storage changes or other provider charges. Check Render pricing again before applying the Blueprint.
3. In the API service environment, set `CORS_ORIGINS` to a JSON array containing the exact Vercel origin, for example `["https://annadan.vercel.app"]`. Set `FRONTEND_BASE_URL` to the same origin. Add `https://` and no trailing slash. Include local origins only if you deliberately need them.
4. Render generates `SECRET_KEY` and injects the private database connection string. Do not expose `DATABASE_URL` or provider secrets in frontend code.
5. Wait for deployment health check `/ready` to pass. The default API base URL in `js/api.js` is `https://annadan-api.onrender.com/api/v1`. If Render assigns a different service hostname, update that one default before deploying the frontend.

**Provider environment variables on Render:**

| Feature | Render variables | Provider setup needed |
|---|---|---|
| Email OTP + email updates | `RESEND_API_KEY`, `EMAIL_FROM` | Resend API key and a sender identity permitted by Resend. For real production recipients, configure/verify your sender domain. |
| SMS alerts + phone OTP | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_VERIFY_SERVICE_SID` | Twilio account, messaging sender and Verify service. Trial accounts may restrict recipients. |
| Food image storage | `CLOUDINARY_URL` | Cloudinary account URL/API credentials. Keep the value only on Render. |
| Voluntary contribution | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Razorpay account; start with test keys. |

Production defaults in `render.yaml` require email verification and administrator food-safety review. Phone verification is optional by default; enable it only after Twilio Verify is configured.

### 3. Deploy the frontend on Vercel

1. In Vercel, choose **Add New → Project** and import the same GitHub repository.
2. Set the **Root Directory** to the repository root (the folder containing `index.html`). Choose **Other** / static site. No build command is required; the output is the project root.
3. Deploy. Vercel assigns a free `*.vercel.app` address; no custom domain is required. If you rename the project, copy the actual assigned origin.
4. Go back to Render and make sure `CORS_ORIGINS` and `FRONTEND_BASE_URL` exactly match that Vercel origin. Redeploy the API after changing them.

### 4. Create the first administrator

In the Render API service, open **Shell** and run from its configured `backend` root:

```bash
python -m app.scripts.create_admin
```

Use a strong unique password. Do not register an admin through the public form.

### 5. Configure Razorpay webhook (when enabling contributions)

In Razorpay test mode, add the webhook URL `https://annadan-api.onrender.com/api/v1/payments/webhook` (replace with the actual Render hostname), subscribe to `payment.captured`, and copy the webhook secret into Render as `RAZORPAY_WEBHOOK_SECRET`. Test a small contribution before switching to live keys.

### 6. Verify deployment

- Frontend: open the Vercel URL.
- API docs: `https://<your-render-service>.onrender.com/docs`.
- Liveness: `/health`; database readiness: `/ready`.
- Test donor registration, email OTP, a donation, an approved receiver request, partner claim, GPS location sharing and admin safety review.

## Optional Google Maps

The delivery map works without a paid map key using Leaflet + OpenStreetMap. To use Google Maps instead, add a browser Maps JavaScript API key to `js/public-config.js` as `window.ANNADAN_GOOGLE_MAPS_API_KEY`. Restrict that key to the actual Vercel referrer and only the Maps JavaScript API. Never place a server-side Google key in this public file. Without a key, the OpenStreetMap map remains active.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

## Important operational limitations

- **Deployment is not performed by this package.** You must connect your own GitHub, Vercel, Render and service-provider accounts and set the secret values.
- Browser GPS requires user permission and a secure HTTPS origin in production. The delivery partner must keep the page open while sharing; this is not background GPS tracking from a closed browser or mobile app. Location is visible only to the handover participants/admin and the latest location is deleted when marked delivered.
- The map route is visual location display, not turn-by-turn navigation or an ETA calculation.
- Food-safety review is an admin checklist/decision, not independent laboratory validation or statutory certification.
- Razorpay is only for voluntary platform support; food donation remains free. Provider fees, onboarding, compliance and eligibility depend on provider accounts and their terms.
- Before production launch, complete a privacy review, rate limiting, security testing, backups/restore drills, audit monitoring, incident response and appropriate legal/food-safety review for the operating region.

# CocoGuard Deployment Guide (Render + Cloudflare Pages)

## 1. GitHub Repositories
- Create two repos:
  - `cocoguard-backend` (this folder)
  - `cocoguard_web` (web frontend)
- Add/commit/push all files except those ignored by `.gitignore`.

## 2. Backend: Deploy to Render
- Go to https://dashboard.render.com/
- Click **New +** → **Web Service**
- Connect your `cocoguard-backend` repo
- Set environment:
  - **Runtime:** Python
  - **Build Command:** `./build.sh` (or `pip install -r requirements.txt && mkdir -p uploads/files uploads/scans`)
  - **Start Command:** `gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120`
  - **Environment Variables:**
    - `DATABASE_URL` (auto-set if you add a Render Postgres DB)
    - `SECRET_KEY` (generate a long random string)
    - `ALGORITHM=HS256`
    - `ACCESS_TOKEN_EXPIRE_MINUTES=1440`
    - `MAX_UPLOAD_SIZE=5242880`
    - `UPLOAD_DIR=./uploads`
    - `ALLOWED_ORIGINS_RAW=*`
    - SMTP/Twilio vars as needed
- Add a **free Postgres database** (Render → Databases → New Database)
- The `render.yaml` file allows you to deploy with Render Blueprints (optional, advanced)
- **Model files:** Already included in `assets/model/` in the repo
- **Health check path:** `/health`

## 3. Web Frontend: Deploy to Cloudflare Pages
- Go to https://pages.cloudflare.com/
- Click **Create a Project**
- Connect your `cocoguard_web` repo
- **Framework preset:** None (static)
- **Build command:** (leave blank)
- **Output directory:** `.`
- Add `_headers` and `_redirects` for SPA and caching
- After deploy, set the API URL in `api-client.js` (see below)

## 4. API URL Configuration
- In `cocoguard_web/api-client.js`, set your Render backend URL:
  ```js
  const PRODUCTION_API_URL = 'https://cocoguard-api.onrender.com';
  ```
- Or, after deploy, open browser console and run:
  ```js
  localStorage.setItem('api_base_url', 'https://cocoguard-api.onrender.com')
  ```

## 5. Environment Variables
- Copy `.env.example` to `.env` for local dev
- On Render, set all secrets in the dashboard (never commit `.env` with secrets)

## 6. Database Migrations
- Alembic is included for schema migrations (see `alembic.ini` if present)
- For first deploy, tables auto-create on startup

## 7. Model Files
- `assets/model/best_float16.tflite` and `labels.txt` are included in the backend repo
- No extra steps needed

## 8. Security
- Never commit `.env` or credentials
- SMTP/Twilio/Firebase secrets must be set in Render dashboard

## 9. Troubleshooting
- Check Render logs for errors
- If model not found: ensure `assets/model/` exists in the deployed repo
- If database errors: check `DATABASE_URL` and DB status

---

For help, see the README or ask your developer.

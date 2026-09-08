# Render.com Deployment Guide — Django + PostgreSQL

## Overview

The Meal Ingestion Pipeline now runs as a single Django monolith on Render:
- **Web service**: Django with Gunicorn (templates + API + static files)
- **Database**: Managed PostgreSQL
- **Zero complexity**: No npm, Vite, or separate frontend build

## Prerequisites

1. **GitHub Repository**: Configured with all Django code
2. **Render Account**: Create free account at [render.com](https://render.com)
3. **API Keys**: Groq, NVIDIA, Google OAuth credentials

## Deployment Steps

### 1. Create PostgreSQL Database

1. Go to Render dashboard → **New +** → **PostgreSQL**
2. Set:
   - Database name: `meal_db`
   - Region: Choose your region
   - Plan: **Standard** (or Starter for testing)
3. Click **Create Database**
4. Copy the connection string (auto-added as `DATABASE_URL`)

### 2. Create Web Service

1. Go to Render dashboard → **New +** → **Web Service**
2. Connect to GitHub repository
3. Configure:
   - **Name**: `meal-system`
   - **Environment**: `Python 3.11`
   - **Root Directory**: Leave empty (project root)
   - **Build Command**:
     ```
     pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
     ```
   - **Start Command**:
     ```
     gunicorn meal_system.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2 --timeout 120
     ```
   - **Plan**: Standard (or Starter for testing)
   - **Region**: Same as database

### 3. Set Environment Variables

In Render dashboard → Web Service → Environment, add:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | `False` |
| `GROQ_API_KEY` | From https://console.groq.com |
| `LLM_MODEL` | `openai/gpt-oss-120b` |
| `NVIDIA_API_KEY` | From https://build.nvidia.com |
| `NVIDIA_ASR_FUNCTION_ID` | Your Parakeet function ID |
| `NVIDIA_API_BASE_URL` | `https://integrate.api.nvidia.com/v1` |
| `NVIDIA_ASR_GRPC_URI` | `grpc.nvcf.nvidia.com:443` |
| `NVIDIA_ASR_LANGUAGE_CODE` | `en-US` |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console |

**Note**: `DATABASE_URL` is auto-linked from PostgreSQL service.

### 4. Deploy

1. Click **Deploy**
2. Monitor build logs in Render dashboard
3. Once "Build successful", your app is live at `https://meal-system.onrender.com`

## Verification Checklist

After deployment:

- [ ] App loads at `https://meal-system.onrender.com`
- [ ] Login page accessible at `/login`
- [ ] Registration form at `/register`
- [ ] Google Sign-In button renders
- [ ] Audio recorder on dashboard
- [ ] Voice upload works end-to-end
- [ ] Meals saved to PostgreSQL and displayed
- [ ] No 500 errors in Render logs

## Troubleshooting

### "psycopg connection failed"
- Verify `DATABASE_URL` is set in Render environment
- PostgreSQL database might still be initializing (wait 1-2 min)
- Redeploy the web service

### "ModuleNotFoundError: No module named 'django'"
- Check `requirements.txt` exists at repo root
- Verify build command includes `pip install -r requirements.txt`
- Redeploy

### "No such table: accounts_user"
- Migrations may not have run (check build logs)
- Manual fix: Render dashboard → Shell → `python manage.py migrate`

### Static files 404 (CSS/JS not loading)
- Verify build command runs `python manage.py collectstatic --noinput`
- Redeploy

### Google OAuth fails
- Verify `GOOGLE_CLIENT_ID` in Render environment
- Update Google Cloud Console authorized redirect URIs:
  - Add: `https://meal-system.onrender.com/login`
  - Add: `https://meal-system.onrender.com/`

## Auto-Deploy

Render auto-deploys when you push to `main` branch. To disable:
- Render dashboard → Settings → Disable auto-deploy

## Scaling

Once deployed, scale up:
1. Render dashboard → Web Service → Plan
2. Upgrade to **Standard** or **Premium**

## Summary

Your Django meal tracking app is now live at https://meal-system.onrender.com and auto-deploys on every push!

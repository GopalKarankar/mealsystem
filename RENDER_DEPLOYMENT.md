# Render.com Deployment Guide

This guide walks through deploying the Meal Ingestion Pipeline (frontend + backend) to Render.com.

## Prerequisites

1. **GitHub Repository**: Push code to GitHub (Render deploys from Git)
2. **Render Account**: Create free account at [render.com](https://render.com)
3. **Environment Variables**: All `.env.example` values must be configured in Render

## Deployment Steps

### Option A: Using render.yaml (Recommended)

The `render.yaml` file at the project root defines both services. Render will auto-detect and deploy:

1. **Connect GitHub**:
   - In Render dashboard: New → Blueprint
   - Select GitHub repo
   - Render auto-deploys from `render.yaml`

2. **Configure Environment Variables**:
   - Go to Render dashboard → Your Blueprint
   - Add these in **Environment** section:
     - `VITE_API_BASE_URL`: `https://meal-system-backend.onrender.com` (update to your backend URL)
     - `VITE_GOOGLE_CLIENT_ID`: Your Google OAuth Client ID
     - `MONGODB_URL`: Your MongoDB connection string
     - `GROQ_API_KEY`: Free from [console.groq.com](https://console.groq.com)
     - `NVIDIA_API_KEY`: From [build.nvidia.com](https://build.nvidia.com)
     - `NVIDIA_ASR_FUNCTION_ID`: Parakeet ASR model ID from NVIDIA
     - `GOOGLE_CLIENT_ID`: From Google Cloud Console
     - `GOOGLE_CLIENT_SECRET`: From Google Cloud Console
     - `SECRET_KEY`: Generate a secure random string (e.g., `openssl rand -hex 32`)

3. **Deploy**:
   - Click "Deploy Blueprint"
   - Render builds and deploys both services
   - Frontend accessible at `https://meal-system-frontend.onrender.com`
   - Backend at `https://meal-system-backend.onrender.com`

### Option B: Manual Setup (One service at a time)

#### 1. Deploy Backend (FastAPI)

**New Web Service**:
- **Name**: `meal-system-backend`
- **GitHub Repo**: Your repo
- **Root Directory**: `backend`
- **Runtime**: Python
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000`

**Environment Variables**:
```
MONGODB_URL=<your-mongodb-connection-string>
MONGODB_DB_NAME=meal_system
SECRET_KEY=<generate-secure-random-string>
GROQ_API_KEY=<your-groq-api-key>
NVIDIA_API_KEY=<your-nvidia-api-key>
NVIDIA_ASR_FUNCTION_ID=<your-parakeet-model-id>
NVIDIA_API_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_ASR_GRPC_URI=grpc.nvcf.nvidia.com:443
NVIDIA_ASR_LANGUAGE_CODE=en-US
DEBUG=False
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
```

Note the Backend URL after deployment (e.g., `https://meal-system-backend.onrender.com`)

#### 2. Deploy Frontend (React + Vite)

**New Web Service**:
- **Name**: `meal-system-frontend`
- **GitHub Repo**: Your repo
- **Root Directory**: `frontend`
- **Runtime**: Node
- **Build Command**: `npm install && npm run build`
- **Start Command**: `npm start`

**Environment Variables**:
```
VITE_API_BASE_URL=https://meal-system-backend.onrender.com
VITE_API_TIMEOUT=30000
VITE_GOOGLE_CLIENT_ID=<your-google-client-id>
NODE_ENV=production
```

**Important**: These are build-time variables (set during build). Render will rebuild when you change them.

## Verification Checklist

After deployment:

- [ ] Frontend loads at `https://meal-system-frontend.onrender.com`
- [ ] Backend API responds at `/docs` endpoint
- [ ] Google sign-in button appears
- [ ] Google OAuth flow completes (users created in MongoDB)
- [ ] Voice recording works end-to-end
- [ ] Meals saved to MongoDB and displayed
- [ ] No console errors in browser DevTools
- [ ] Network requests to backend succeed (check Network tab)

## Troubleshooting

### Frontend blank page / 404
- Check Render logs: Dashboard → Frontend Service → Logs
- Verify `VITE_API_BASE_URL` is set correctly
- Ensure `npm run build` creates `dist/` folder

### Backend 503 Service Unavailable
- Check Render backend logs
- Verify all environment variables are set
- Ensure MongoDB connection string is correct
- Check if Groq/NVIDIA APIs are accessible

### Google OAuth fails
- Verify `VITE_GOOGLE_CLIENT_ID` matches backend's `GOOGLE_CLIENT_ID`
- Update Google Cloud Console authorized redirect URIs:
  - Add: `https://meal-system-backend.onrender.com/auth/google/callback`
  - Add: `https://meal-system-frontend.onrender.com`

### MongoDB connection fails
- Check connection string format: `mongodb+srv://user:password@cluster.mongodb.net/`
- Verify IP whitelist (if using Atlas)
- Test locally first: `python -c "from pymongo import MongoClient; MongoClient('<url>').admin.command('ping')"`

### Voice transcription fails
- Verify `NVIDIA_ASR_FUNCTION_ID` is correct
- Test NVIDIA API locally (see backend docs)
- Check backend logs for gRPC errors

## CI/CD & Auto-Deploys

Render auto-deploys when you push to `main` branch. To disable:
- Dashboard → Service → Settings → Auto-Deploy → Off

To manual deploy:
- Push to `main` and Render redeploys automatically

## Scaling & Limits

Render free tier includes:
- 750 hours/month combined for all services
- 0.5 GB RAM per service (enough for this app)
- 1 GB storage (MongoDB)

For production:
- Upgrade to Starter/Standard plans
- Add health checks (Render dashboard → Health Checks)
- Enable automatic restarts on crashes

## Next Steps

1. Set up MongoDB (Atlas free tier or Render database)
2. Get API keys (Groq, NVIDIA, Google)
3. Push to GitHub
4. Deploy via Render dashboard
5. Test end-to-end
6. Monitor logs and errors

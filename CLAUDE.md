# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

**Project**: Meal Ingestion Pipeline — Voice-to-meal-data web app  
**Stack**: React 19 + Vite + Tailwind | FastAPI + MongoDB (PyMongo)  
**Deadline**: September 12, 2026  
**Spec**: See [SPEC.md](./SPEC.md) for full 15-section product specification

---

## Development Setup

### Before First Run

1. **Clone and navigate**:
   ```bash
   git clone <repo>
   cd meal-system
   ```

2. **Frontend setup**:
   ```bash
   cd frontend
   cp .env.example .env
   npm install
   ```

3. **Start MongoDB** (via Docker):
   ```bash
   docker run -d --name meal-mongo -p 27017:27017 mongo:7
   ```

4. **Backend setup**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   ```
   
   **System dependencies** (required for audio transcoding):
   - `ffmpeg` must be installed and on `PATH` (used to transcode MP3/M4A/WebM → WAV for Parakeet ASR)
   - On macOS: `brew install ffmpeg`
   - On Ubuntu/Debian: `apt-get install ffmpeg`
   - On Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use `winget install ffmpeg`

5. **Start both servers** (open two terminals):
   ```bash
   # Terminal 1: Frontend
   cd frontend && npm run dev        # http://localhost:5173

   # Terminal 2: Backend
   cd backend && python main.py      # http://localhost:8000
   ```

### Environment Variables

**Frontend** (`frontend/.env`):
- `VITE_API_BASE_URL` — Backend API (default: http://localhost:8000)
- `VITE_API_TIMEOUT` — Request timeout in ms (default: 30000)
- `VITE_GOOGLE_CLIENT_ID` — Google OAuth client ID (get from [Google Cloud Console](https://console.cloud.google.com))

**Backend** (`backend/.env`):
- `SECRET_KEY` — JWT secret (change in production)
- `GROQ_API_KEY` — Groq API key (get free key from console.groq.com, used for Llama LLM parsing)
- `MONGODB_URL` — MongoDB connection string (default: mongodb://localhost:27017)
- `MONGODB_DB_NAME` — MongoDB database name (default: meal_system)
- `NVIDIA_API_KEY` — NVIDIA API key (get from [build.nvidia.com](https://build.nvidia.com), used for Parakeet ASR)
- `NVIDIA_API_BASE_URL` — NVIDIA NIM API endpoint (default: https://integrate.api.nvidia.com/v1)
- `NVIDIA_ASR_FUNCTION_ID` — Parakeet ASR model function ID (copy from build.nvidia.com for your chosen variant, required for voice transcription)
- `NVIDIA_ASR_GRPC_URI` — Parakeet ASR gRPC endpoint (default: grpc.nvcf.nvidia.com:443)
- `NVIDIA_ASR_LANGUAGE_CODE` — Language code for transcription (default: en-US)
- `DEBUG` — Set to False in production
- `GOOGLE_CLIENT_ID` — Google OAuth client ID (from Google Cloud Console)
- `GOOGLE_CLIENT_SECRET` — Google OAuth client secret (from Google Cloud Console)

### Google OAuth 2.0 Setup

#### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (e.g., "Meal System")
3. Enable the **Google+ API** (Search → "Google+ API" → Enable)
4. Create OAuth 2.0 credentials:
   - Go to **Credentials** → **Create Credentials** → **OAuth client ID**
   - Choose **Web application**
   - Add authorized JavaScript origins:
     - `http://localhost:5173` (dev frontend)
     - `http://localhost` (dev fallback)
   - Add authorized redirect URIs:
     - `http://localhost:8000/auth/google/callback` (dev backend)
   - Copy **Client ID** and **Client Secret** to `.env` files

#### 2. Frontend Setup

Install `@react-oauth/google`:
```bash
cd frontend
npm install @react-oauth/google
```

Wrap your app with `GoogleOAuthProvider` in `main.jsx`:
```jsx
import { GoogleOAuthProvider } from '@react-oauth/google';
import App from './App';

ReactDOM.render(
  <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
    <App />
  </GoogleOAuthProvider>,
  document.getElementById('root')
);
```

Add Google Login button in `Login.jsx`:
```jsx
import { GoogleLogin } from '@react-oauth/google';

export default function Login() {
  const handleGoogleLogin = async (credentialResponse) => {
    // Send idToken to backend for verification
    const res = await api.post('/auth/google', {
      id_token: credentialResponse.credential
    });
    // Store JWT token from backend
    localStorage.setItem('access_token', res.data.access_token);
    // Redirect to dashboard
    navigate('/dashboard');
  };

  return (
    <GoogleLogin
      onSuccess={handleGoogleLogin}
      onError={() => console.log('Login failed')}
      theme="outline"
      size="large"
    />
  );
}
```

#### 3. Backend Setup

Install dependencies:
```bash
cd backend
pip install google-auth google-auth-httplib2 google-auth-oauthlib
# Or use: pip install google-auth==2.25.2
```

Add Google OAuth endpoint in `backend/app/routes/auth.py`:
```python
from google.auth.transport import requests
from google.oauth2 import id_token
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

class GoogleLoginRequest(BaseModel):
    id_token: str

@router.post('/google')
async def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Verify Google ID token and create/return user with JWT."""
    try:
        # Verify token with Google
        idinfo = id_token.verify_oauth2_token(
            request.id_token,
            requests.Request(),
            current_app.config['GOOGLE_CLIENT_ID']
        )
        
        # Extract user info
        email = idinfo['email']
        name = idinfo['name']
        google_id = idinfo['sub']
        
        # Find or create user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                username=email.split('@')[0],
                full_name=name,
                google_id=google_id
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Generate JWT token
        access_token = create_access_token(data={'sub': user.id})
        return {
            'access_token': access_token,
            'token_type': 'bearer',
            'user_id': user.id
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail='Invalid token')
```

#### 4. MongoDB Document Structure

User documents in MongoDB simply include a `google_id: Optional[str]` key (set to `None` at registration, and set via `$set` on first Google login) — there is no ORM model file to edit. Documents are stored in the `users` collection and have the following shape:
```json
{
  "_id": ObjectId,
  "username": "string",
  "email": "string",
  "password_hash": "string (or null for OAuth-only users)",
  "google_id": "string (or null)",
  "created_at": datetime,
  "updated_at": datetime
}
```

---

## Common Development Tasks

### Run Dev Servers

```bash
# Frontend (http://localhost:5173)
cd frontend && npm run dev

# Backend (http://localhost:8000)
cd backend && python main.py

# API docs (Swagger)
open http://localhost:8000/docs
```

### Linting & Formatting

```bash
# Frontend
cd frontend
npm run lint          # Check for issues
npm run format        # Auto-format code

# Backend
cd backend
python -m flake8 app/
python -m black app/  # Auto-format
```

### Testing

```bash
# Frontend
cd frontend
npm test              # Run Jest tests
npm test -- --watch  # Watch mode

# Backend
cd backend
pytest                # All tests
pytest tests/test_auth.py -v  # Single file, verbose
pytest tests/ -k "test_login" # Filter by name
pytest --cov app/    # Coverage report
```

### Database (MongoDB)

MongoDB is schemaless — no migration step for document changes.

#### Reset local dev data

To reset all data (meals and meals history):
```bash
docker exec meal-mongo mongosh meal_system --eval "db.dropDatabase()"
```

### Build for Production

```bash
# Frontend
cd frontend
npm run build         # Creates dist/

# Backend
cd backend
# Set DEBUG=False in .env, then deploy with:
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

---

## Architecture Overview

### Frontend Structure

```
frontend/src/
├── components/
│   ├── common/        # Reusable: Button, Card, Badge, Spinner
│   ├── audio/         # AudioRecorder (main feature)
│   ├── meal/          # MealCard, MealItem, NutritionBreakdown
│   ├── dashboard/     # DailySummary, MacroChart, MealList
│   └── layout/        # Header, Footer, Container
├── pages/
│   ├── Login.jsx      # Auth page
│   ├── Register.jsx   # Sign-up
│   └── Dashboard.jsx  # Main app (meals + charts)
├── store/
│   └── mealsStore.js  # Zustand: meals state, CRUD actions
├── utils/
│   ├── api.js         # Axios client with JWT interceptor
│   ├── auth.js        # Token management
│   ├── nutrition.js   # Macro calculations
│   └── formatting.js  # Date/number formatting
└── styles/
    ├── globals.css    # Tailwind + resets
    ├── variables.css  # Design tokens (colors, spacing, shadows)
    └── animations.css # Keyframes (spin, fade, slide)
```

**Key Patterns**:
- **State**: Zustand store for meals (lightweight, no Redux boilerplate)
- **API**: Axios with auto-auth interceptor (JWT in header)
- **Styling**: Tailwind utilities + CSS variables for design tokens
- **Auth**: JWT stored in localStorage, cleared on 401

### Backend Structure

```
backend/
├── main.py            # FastAPI app, routes, middleware setup
├── pytest.ini         # pytest configuration
├── app/
│   ├── config.py      # Settings from .env (using Pydantic)
│   ├── database.py    # PyMongo client, get_db()
│   ├── schemas.py     # Pydantic: request/response validation
│   ├── auth/
│   │   ├── password.py # bcrypt: hash_password(), verify_password()
│   │   ├── jwt.py      # create_access_token(), decode_access_token()
│   │   ├── dependencies.py # get_current_user() — auth decorator
│   │   └── google_oauth.py # Google OAuth helper
│   ├── routes/
│   │   ├── auth.py     # POST /auth/register, /auth/login, /auth/google
│   │   └── meals.py    # GET/POST/PATCH/DELETE /meals
│   └── services/
│       ├── whisper_service.py # transcribe(audio_file) → text
│       ├── llm_service.py     # parse_meal(transcript) → JSON
│       ├── nutrition_service.py # validate_macros() — arithmetic sanity check
│       └── meal_service.py     # create_meal_from_audio(), replace_meal_items(), business logic
├── tests/
│   ├── __init__.py
│   ├── conftest.py    # pytest fixtures (test database)
│   └── test_meal_service.py
└── requirements.txt   # FastAPI, PyMongo, pytest, etc.
```

**Key Patterns**:
- **Async**: FastAPI async/await throughout (fast AI/ML pipelines)
- **Validation**: Pydantic schemas validate all requests
- **Auth**: JWT middleware checks token, injects get_current_user
- **Services**: Layer between routes (API) and models (DB)
- **Error Handling**: HTTPException with clear messages, logged
- **Nutrition**: Meal item macros/confidence come directly from the Groq Llama parse (`llm_service.py`), sanity-checked (not overridden) by `nutrition_service.validate_macros()`'s ±10% calorie-arithmetic check

---

## API Endpoints (Quick Reference)

**Auth**:
```
POST   /auth/register      → { access_token, token_type, user_id }
POST   /auth/login         → { access_token, token_type, user_id }
```

**Meals**:
```
POST   /meals/voice        → { meal_id, meal_items[], totals, confidence_score }
GET    /meals?date=YYYY-MM-DD&limit=50
PATCH  /meals/{id}         → Updated meal
DELETE /meals/{id}         → 204 No Content
GET    /dashboard          → { today, week, recent_meals }
```

Full spec: See [SPEC.md](./SPEC.md) § 5 (API Specification)

---

## Design System

**Colors** (defined in `frontend/src/styles/variables.css`):
- **Macros**: Orange (#F97316) = Protein, Blue (#3B82F6) = Carbs, Gold (#D97706) = Fats
- **Status**: Green (#2E7D32) = Success, Red (#D32F2F) = Error, Amber (#F97316) = Warning
- **Base**: White (#FFFFFF) text on Deep Black (#1A1A1A)

**Spacing** (8px grid): xs=4px, sm=8px, md=16px, lg=24px, xl=32px

**Components**: Use Tailwind classes with custom colors; refer to Tailwind config for brand colors.

Full design system: See [SPEC.md](./SPEC.md) § 3 (Visual Design System)

---

## High-Level Code Flow

### Voice Meal Ingestion (Core Feature)

```
User (Frontend)
  ↓ 1. Click "Record Meal"
AudioRecorder Component
  ↓ 2. Record voice → .wav file
  ↓ 3. POST /meals/voice (multipart/form-data)
Backend: POST /meals/voice
  ↓ 4. Save audio temporarily
  ↓ 5. Call Groq Whisper-large-v3 → transcript
  ↓ 6. Call Groq Llama-3.3-70B with system prompt → structured JSON with LLM-estimated macros
  ↓ 7. Pydantic validation (schema, ranges)
  ↓ 8. Validate macros (calories ≈ P*4 + C*4 + F*9)
  ↓ 9. Save Meal + MealItems to DB
  ↓ 10. Delete temp audio, return JSON
Frontend: useMealsStore.addMeal()
  ↓ 11. Update UI (MealCard appears)
  ↓ 12. User can edit/delete/continue
```

**Validation Checkpoints**:
1. Audio format (mp3, wav, m4a, webm), size < 25MB
2. Whisper success (timeout 30s)
3. LLM JSON validity (all fields present, valid types)
4. Macro sanity (±10% tolerance on kcal calculation)
5. Confidence scoring (0.0-1.0 per item)

See [SPEC.md](./SPEC.md) § 8 (LLM Prompting) for Groq system prompt.

---

## Testing Strategy

### Frontend
- **Component tests**: Render + simulate user actions (Jest + React Testing Library)
- **API mocking**: Mock axios responses in tests
- **E2E (optional)**: Playwright for full flows

### Backend
- **Unit tests**: Each service function tested independently
- **Integration tests**: Auth flow, DB operations, API endpoints
- **Fixtures**: Mock Whisper/Claude responses
- **Coverage target**: >80%

**Example test**:
```python
def test_voice_endpoint_valid_audio(client, auth_headers):
    with open("tests/fixtures/sample_meal.wav", "rb") as f:
        response = client.post(
            "/meals/voice",
            files={"audio": f},
            headers=auth_headers
        )
    assert response.status_code == 201
    assert response.json()["confidence_score"] > 0.7
```

### Google OAuth Testing

**Backend OAuth endpoint test**:
```python
from unittest.mock import patch

def test_google_login_new_user(client, db):
    """Test Google OAuth login creates new user."""
    mock_idinfo = {
        'sub': 'google_123',
        'email': 'user@gmail.com',
        'name': 'Test User'
    }
    
    with patch('google.oauth2.id_token.verify_oauth2_token', return_value=mock_idinfo):
        response = client.post(
            '/auth/google',
            json={'id_token': 'mock_token'}
        )
    
    assert response.status_code == 200
    assert 'access_token' in response.json()
    
    # Verify user created in DB
    user = db.query(User).filter(User.email == 'user@gmail.com').first()
    assert user is not None
    assert user.google_id == 'google_123'

def test_google_login_existing_user(client, db):
    """Test Google OAuth login returns existing user."""
    user = User(email='existing@gmail.com', google_id='google_456')
    db.add(user)
    db.commit()
    
    mock_idinfo = {
        'sub': 'google_456',
        'email': 'existing@gmail.com',
        'name': 'Existing User'
    }
    
    with patch('google.oauth2.id_token.verify_oauth2_token', return_value=mock_idinfo):
        response = client.post(
            '/auth/google',
            json={'id_token': 'mock_token'}
        )
    
    assert response.status_code == 200
    assert response.json()['user_id'] == user.id

def test_google_login_invalid_token(client):
    """Test Google OAuth rejects invalid tokens."""
    with patch('google.oauth2.id_token.verify_oauth2_token', side_effect=ValueError):
        response = client.post(
            '/auth/google',
            json={'id_token': 'invalid_token'}
        )
    
    assert response.status_code == 401
```

**Frontend OAuth component test** (React Testing Library):
```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Login from './Login';

jest.mock('@react-oauth/google', () => ({
  GoogleLogin: ({ onSuccess }) => (
    <button onClick={() => onSuccess({ credential: 'mock_token' })}>
      Sign in with Google
    </button>
  )
}));

test('Google login submits token to backend', async () => {
  render(<Login />);
  
  fireEvent.click(screen.getByText('Sign in with Google'));
  
  await waitFor(() => {
    expect(localStorage.getItem('access_token')).toBe('mock_jwt_token');
  });
});
```

---

## Common Pitfalls & Debugging

### "Meal confidence score is too low"
- Check Groq Llama prompt (backend/app/services/llm_service.py)
- Vague transcripts ("I ate stuff") get low confidence
- Fallback: user can edit before saving

### "Macro calculations don't match"
- Claude might round differently; allow ±10% tolerance
- Check validation logic in backend/app/services/nutrition_service.py
- Log request/response for debugging

### "Audio upload fails"
- Frontend: Check browser console (Dev Tools → Network)
- Backend: Check if Parakeet is configured (`NVIDIA_ASR_FUNCTION_ID` set), NVIDIA API key works
- Non-WAV uploads (MP3, M4A, WebM) are automatically transcoded to WAV; ensure `ffmpeg` is installed and on `PATH`
- If transcoding fails ("ffmpeg not found" or "unsupported audio codec"), install ffmpeg or check audio format validity
- Test with curl: `curl -F "audio=@sample.wav" http://localhost:8000/meals/voice` (requires auth header: `-H "Authorization: Bearer <jwt_token>"`)

### "JWT token expired"
- Frontend: Auto-logout on 401 (axios interceptor)
- Check token in localStorage: `localStorage.getItem('access_token')`
- Login again to get fresh token

### "Cannot connect to MongoDB"
- Check Docker container is running: `docker ps | grep meal-mongo`
- Verify `MONGODB_URL` in `.env` matches the running container's port
- Backend fails fast at startup with a ping error if Mongo is unreachable — check console output

### Google OAuth Troubleshooting

### "Google sign-in button not appearing"
- Check `VITE_GOOGLE_CLIENT_ID` is set in `frontend/.env`
- Verify `@react-oauth/google` is installed: `npm list @react-oauth/google`
- Check console (Dev Tools → Console) for errors
- Ensure `GoogleOAuthProvider` wraps the component tree in `main.jsx`

### "401 Invalid token from Google backend"
- Verify `GOOGLE_CLIENT_ID` in backend `.env` matches frontend
- Check Google Cloud Console: Credentials → OAuth 2.0 Client IDs
- Ensure authorized redirect URIs include `http://localhost:8000/auth/google/callback`
- Test token verification: `python -c "from google.oauth2 import id_token; print('Import OK')"`

### "CORS error on /auth/google request"
- Backend must include CORS headers for frontend origin
- Add to `main.py`:
  ```python
  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173", "http://localhost:3000"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```

### "User created but not logging in consistently"
- Check `google_id` is persisted in DB (run: `docker exec meal-mongo mongosh meal_system --eval "db.users.find({}, {google_id:1})"`)
- Verify User documents include `google_id` field in MongoDB
- Test lookup: `docker exec meal-mongo mongosh meal_system --eval "db.users.findOne({email: 'test@example.com'})"` should return the document

### "Token still valid after logout"
- Implement token blacklist or short expiry (recommend 15min)
- Frontend: Always delete token on logout: `localStorage.removeItem('access_token')`
- Add logout endpoint to clear server-side sessions (if using)

---

## Accessibility & Responsive Design

**Mobile-first approach**:
- Test at 375px (base mobile), 600px (tablet), 1024px (desktop)
- Touch targets: 44px minimum
- Text contrast: 4.5:1 (AA standard)

**Testing keyboard navigation**:
- Tab through all buttons/inputs
- Focus states must be visible
- No keyboard traps

**Screen readers**:
- Use semantic HTML (button, input, label)
- Add `aria-label` to icon buttons
- Test with NVDA (Windows) or VoiceOver (Mac)

See [SPEC.md](./SPEC.md) § 11 (Accessibility Standards) for full WCAG checklist.

---

## Git Workflow

**Branch naming**:
```
feature/voice-upload      (new feature)
fix/confidence-validation (bug fix)
refactor/meal-service     (cleanup)
docs/api-endpoints        (documentation)
```

**Commit messages**:
```
feat: Add voice recording UI component
fix: Validate macro totals within ±10%
refactor: Extract nutrition logic to service
docs: Update API endpoint reference
```

**Before pushing**:
```bash
# Frontend
npm run lint && npm run format

# Backend
python -m black app/
python -m flake8 app/
pytest

# Both
git log --oneline -n 5
```

---

## Production Build & Render.com Deployment

### Frontend Build for Production

```bash
cd frontend
npm install              # Install all dependencies
npm run build          # Creates dist/ folder with optimized assets
npm start              # Test production server locally (port 5173)
```

**Key Files**:
- `server.js` — Production Express server (serves `dist/`, handles SPA routing)
- `vite.config.js` — Build config (minification, chunk splitting)
- `.env.example` — Environment variables template (update production URLs here)

**Frontend Production Environment**:
- `VITE_API_BASE_URL` — Must point to deployed backend (e.g., `https://meal-system-backend.onrender.com`)
- `VITE_GOOGLE_CLIENT_ID` — Same Google Client ID as backend's `GOOGLE_CLIENT_ID`
- `VITE_API_TIMEOUT` — Request timeout in ms (default: 30000)

**Render Deployment**:
- See [RENDER_DEPLOYMENT.md](./RENDER_DEPLOYMENT.md) for full setup
- TL;DR: Push to GitHub → Render auto-deploys from `render.yaml` → Frontend at `https://meal-system-frontend.onrender.com`
- Backend start command: `npm start` (serves via Express from `dist/`)
- Build command: `npm install && npm run build`

### Backend Production

**Start Command** (documented in main.py):
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

**Environment Variables** (set in `.env` for local test, in Render dashboard for production):
- All keys from `backend/.env.example`
- DEBUG must be `False` in production
- MONGODB_URL must point to production database
- All API keys (GROQ, NVIDIA, Google) configured

---

## Deployment Checklist (Pre-Sept 12)

**Frontend (React/Vite)**:
- [ ] `npm run build` succeeds (no errors, creates `dist/`)
- [ ] `npm start` serves built app correctly (Express server running)
- [ ] `.env.example` updated with production comments and defaults
- [ ] No console.log / debug statements in src/
- [ ] ESLint & Prettier pass: `npm run lint && npm run format`
- [ ] All dependencies in package.json (including terser, express)
- [ ] Google sign-in button renders and is clickable
- [ ] VITE_API_BASE_URL correctly points to backend in production
- [ ] VITE_GOOGLE_CLIENT_ID matches backend's GOOGLE_CLIENT_ID

**Backend (FastAPI)**:
- [ ] `pip install -r requirements.txt` works (no missing packages)
- [ ] `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app` starts without errors
- [ ] `.env.example` updated with all required keys (no secrets)
- [ ] No console.log / debug statements
- [ ] Linted & formatted (Black, Flake8, pytest passes)
- [ ] DEBUG=False in production .env
- [ ] All API keys set (GROQ, NVIDIA, Google)
- [ ] MongoDB connection tested from production environment

**End-to-End**:
- [ ] Tests passing (npm test, pytest)
- [ ] MongoDB and Qdrant reachable from production environment
- [ ] README complete (setup instructions + Google OAuth steps)
- [ ] API docs at /docs endpoint
- [ ] Google OAuth tested (token validation, user creation, existing user login)
- [ ] JWT tokens issued after OAuth login
- [ ] CORS configured for frontend/backend OAuth requests
- [ ] Responsive on mobile (375px), tablet (600px), desktop (1024px+)
- [ ] Accessibility tested (keyboard nav, screen reader labels)
- [ ] Error messages user-friendly (not technical)
- [ ] Confidence badges working (green >90%, orange 70-90%, red <70%)
- [ ] Google Client ID/Secret configured in production environment
- [ ] Production redirect URI matches Google Cloud Console settings
- [ ] Token expiry & refresh logic working (or use short-lived tokens)
- [ ] Logout clears token from localStorage and optionally server-side
- [ ] Render.yaml configured (or manual Render setup documented)
- [ ] GitHub repo connected to Render for auto-deploy

See [SPEC.md](./SPEC.md) § 14-15 (QA & Deployment Checklists) for full details.

---

## Useful References

| Topic | Location |
|-------|----------|
| Database schema | [SPEC.md](./SPEC.md) § 4 |
| API contract | [SPEC.md](./SPEC.md) § 5 |
| Claude prompting | [SPEC.md](./SPEC.md) § 8 |
| Error handling | [SPEC.md](./SPEC.md) § 9 |
| Security rules | [SPEC.md](./SPEC.md) § 10 |
| Design tokens | [SPEC.md](./SPEC.md) § 13 |
| Frontend docs | [README.md](./README.md) / `frontend/` |
| Backend docs | [README.md](./README.md) / `backend/` |
| Google OAuth setup | See "Google OAuth 2.0 Setup" above (§ this file) |
| Render deployment | [RENDER_DEPLOYMENT.md](./RENDER_DEPLOYMENT.md) |
| Google Cloud Console | https://console.cloud.google.com |
| @react-oauth/google docs | https://www.npmjs.com/package/@react-oauth/google |
| google-auth library | https://github.com/googleapis/google-auth-library-python |
| Render.com | https://render.com |

---

## Getting Help

1. **Setup issues**: Check README.md Quick Start section
2. **Code questions**: Review component files (well-structured, short)
3. **API questions**: Hit `/docs` endpoint in browser (Swagger)
4. **Design questions**: See `frontend/src/styles/variables.css`
5. **Architecture questions**: This file + [SPEC.md](./SPEC.md)


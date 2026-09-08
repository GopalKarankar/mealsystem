# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

**Project**: Meal Ingestion Pipeline — Voice-to-meal-data web app  
**Stack**: Django 5 + PostgreSQL + Tailwind | DRF + Gunicorn  
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

2. **Create PostgreSQL database** (via Docker):
   ```bash
   docker run -d --name meal-postgres -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
   ```

3. **Backend setup**:
   ```bash
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

4. **Configure .env**:
   ```bash
   # Copy example and update values
   cp .env.example .env
   # Edit .env with your API keys and database URL:
   # DATABASE_URL=postgresql://postgres:postgres@localhost:5432/meal_system
   ```

5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Start server**:
   ```bash
   python manage.py runserver  # http://localhost:8000
   ```

### Environment Variables

**Backend** (`.env`):
- `SECRET_KEY` — Django secret key (generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DEBUG` — Set to `False` in production
- `DATABASE_URL` — PostgreSQL connection string (default: `postgresql://postgres:postgres@localhost:5432/meal_system`)
- `GROQ_API_KEY` — Groq API key (get free key from console.groq.com, used for Llama LLM parsing)
- `LLM_MODEL` — Groq model ID (default: `openai/gpt-oss-120b`)
- `NVIDIA_API_KEY` — NVIDIA API key (get from [build.nvidia.com](https://build.nvidia.com), used for Parakeet ASR)
- `NVIDIA_API_BASE_URL` — NVIDIA NIM API endpoint (default: `https://integrate.api.nvidia.com/v1`)
- `NVIDIA_ASR_FUNCTION_ID` — Parakeet ASR model function ID (copy from build.nvidia.com for your chosen variant, required for voice transcription)
- `NVIDIA_ASR_GRPC_URI` — Parakeet ASR gRPC endpoint (default: `grpc.nvcf.nvidia.com:443`)
- `NVIDIA_ASR_LANGUAGE_CODE` — Language code for transcription (default: `en-US`)
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
     - `http://localhost:8000` (dev frontend)
     - `http://localhost` (dev fallback)
   - Add authorized redirect URIs:
     - `http://localhost:8000/login` (dev backend)
   - Copy **Client ID** and **Client Secret** to `.env` file

#### 2. Frontend Setup (Django Templates)

Django templates are served from `templates/` directory with Google Identity Services SDK integration.

Update `templates/login.html` to include Google Sign-In button:
```html
<!-- Load Google Identity Services SDK -->
<script src="https://accounts.google.com/gsi/client" async defer></script>

<!-- Initialize and render Google Sign-In button -->
<div id="g_id_onload"
     data-client_id="{{ google_client_id }}"
     data-callback="handleCredentialResponse">
</div>
<div class="g_id_signin" data-type="standard"></div>

<script>
function handleCredentialResponse(response) {
  // Send JWT to backend
  fetch('/auth/google', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      id_token: response.credential
    })
  })
  .then(res => res.json())
  .then(data => {
    // Store token and redirect
    localStorage.setItem('access_token', data.access_token);
    window.location.href = '/';
  });
}
</script>
```

#### 3. Backend Setup (Django + DRF)

Google OAuth verification is configured in `accounts/views.py` and uses the `google-auth` library (already in requirements.txt).

The `GoogleLoginView` verifies the OAuth token:
```python
from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.status import HTTP_401_UNAUTHORIZED
from accounts.models import User

class GoogleLoginView(APIView):
    def post(self, request):
        """Verify Google ID token and create/return user with JWT."""
        try:
            # Verify token with Google
            idinfo = id_token.verify_oauth2_token(
                request.data.get('id_token'),
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
            
            email = idinfo['email']
            google_id = idinfo['sub']
            
            # Find or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': generate_unique_username(email.split('@')[0]),
                    'google_id': google_id
                }
            )
            
            # Update google_id if not set
            if not user.google_id:
                user.google_id = google_id
                user.save()
            
            # Generate JWT token
            access_token = create_access_token({'user_id': user.id})
            return Response({
                'access_token': access_token,
                'token_type': 'Bearer',
                'user_id': user.id,
                'expires_in': 604800
            })
        except ValueError:
            return Response({'detail': 'Invalid token'}, status=HTTP_401_UNAUTHORIZED)
```

---

## Common Development Tasks

### Run Dev Server

```bash
python manage.py runserver  # http://localhost:8000
```

### Linting & Formatting

```bash
python -m black meal_system/ accounts/ meals/  # Auto-format
python -m flake8 meal_system/ accounts/ meals/  # Check for issues
```

### Testing

```bash
pytest                              # All tests
pytest tests/test_auth.py -v        # Single file, verbose
pytest tests/ -k "test_login"       # Filter by name
pytest --cov=accounts --cov=meals   # Coverage report
```

### Database (PostgreSQL)

#### Reset local dev data

To reset all data (users and meals):
```bash
python manage.py flush --no-input
python manage.py migrate
```

#### Create superuser (for admin access)

```bash
python manage.py createsuperuser
```

Then visit `http://localhost:8000/admin` to manage data.

### Build for Production

```bash
# Set DEBUG=False in .env, then deploy with:
gunicorn meal_system.wsgi:application --bind 0.0.0.0:8000 --workers 4 --threads 2 --timeout 120
```

---

## Architecture Overview

### Django Project Structure

```
meal_system/
├── manage.py                  # Django command-line utility
├── meal_system/
│   ├── __init__.py
│   ├── settings.py            # Django configuration, loads .env
│   ├── urls.py                # URL routing (auth, meals, templates)
│   ├── wsgi.py                # WSGI application entry point
│   └── asgi.py                # ASGI application (not used, here for completeness)
├── accounts/
│   ├── models.py              # User model (extends AbstractUser)
│   ├── views.py               # RegisterView, LoginView, GoogleLoginView (APIView)
│   ├── serializers.py         # Pydantic-like validation (DRF serializers)
│   ├── authentication.py      # DRF custom authentication class (Bearer token)
│   ├── jwt.py                 # create_access_token(), decode_access_token()
│   ├── google_oauth.py        # generate_unique_username()
│   ├── urls.py                # Routes to /auth/register, /login, /google
│   └── admin.py               # Django admin config
├── meals/
│   ├── models.py              # Meal, MealItem models
│   ├── views.py               # APIView endpoints (voice, list, update, delete, dashboard)
│   ├── serializers.py         # Meal, MealItem serializers
│   ├── urls.py                # Routes to /meals/*
│   ├── services/
│   │   ├── nutrition_service.py # validate_macros()
│   │   ├── llm_service.py       # parse_meal() — Groq Llama
│   │   ├── whisper_service.py   # transcribe() — NVIDIA Parakeet
│   │   └── meal_service.py      # Business logic: create_meal_from_audio(), replace_meal_items(), etc.
│   └── admin.py               # Django admin config
├── templates/
│   ├── base.html              # Base layout with Chart.js CDN, static JS loader
│   ├── login.html             # Google Sign-In page
│   ├── register.html          # Registration form
│   └── dashboard.html         # Meal tracker dashboard
├── static/
│   └── js/
│       ├── auth.js            # getToken(), setToken(), removeToken(), logout()
│       ├── apiClient.js       # apiRequest(), apiGet/Post/Patch/Delete helpers
│       ├── nutrition.js       # calculateMacroPercentages(), getMacroColor()
│       ├── formatting.js      # formatNumber(), formatTime(), formatDate()
│       ├── audioRecorder.js   # AudioRecorder class (MediaRecorder API)
│       ├── macroChart.js      # MacroChart class (Chart.js doughnut)
│       └── dashboard.js       # Dashboard class (state management, render)
├── tests/
│   ├── conftest.py            # pytest fixtures (test_user, test_user_with_google)
│   ├── test_auth.py           # Auth endpoint tests
│   └── test_meals.py          # Meals endpoint tests
├── .env.example               # Environment variables template
├── requirements.txt           # Django, DRF, psycopg, pytest-django, etc.
└── pytest.ini                 # pytest configuration
```

**Key Patterns**:
- **ORM**: Django ORM (User, Meal, MealItem models with ForeignKey relationships)
- **API**: Django REST Framework APIView subclasses
- **Auth**: Custom DRF authentication class validates Bearer token, returns 401 on failure
- **Services**: Layer between views (API) and models (DB) for business logic
- **Validation**: DRF serializers validate requests/responses
- **Templates**: Django templates + vanilla JavaScript (no React, no Vite build step)
- **Styling**: Tailwind CSS via CDN + vanilla JS

### Database Schema (PostgreSQL)

**accounts_user**:
- `id` (PK, auto-increment)
- `username` (unique, 150 char)
- `email` (unique)
- `password` (bcrypt hash, nullable for OAuth-only)
- `google_id` (nullable, unique)
- `created_at` (auto-now-add)
- `updated_at` (auto-now)

**meals_meal**:
- `id` (PK, auto-increment)
- `user_id` (FK to accounts_user)
- `original_text` (nullable)
- `transcription_text` (nullable)
- `parsed_at` (nullable)
- `created_at` (auto-now-add)
- `updated_at` (auto-now)
- `confidence_score` (float, 0.0-1.0)

**meals_mealitem**:
- `id` (PK, auto-increment)
- `meal_id` (FK to meals_meal)
- `item_name` (string)
- `quantity` (float)
- `unit` (string, e.g., "g", "oz")
- `serving_size_grams` (float, nullable)
- `calories` (float)
- `protein_g` (float)
- `carbs_g` (float)
- `fats_g` (float)
- `fiber_g` (float, default 0)
- `confidence` (float, default 0.85)
- `source` (string, "llm_generated" or "user_input")
- `llm_generated` (bool)
- `created_at` (auto-now-add)

---

## API Endpoints (Quick Reference)

**Auth**:
```
POST   /auth/register      → { access_token, token_type, user_id, expires_in }
POST   /auth/login         → { access_token, token_type, user_id, expires_in }
POST   /auth/google        → { access_token, token_type, user_id, expires_in }
```

**Meals**:
```
POST   /meals/voice        → { meal_id, meal_items[], totals, confidence_score }
GET    /meals?date=YYYY-MM-DD&limit=50
PATCH  /meals/{id}         → Updated meal
DELETE /meals/{id}         → 204 No Content
GET    /dashboard?date=    → { today, week, recent_meals, confidence_distribution }
```

Full spec: See [SPEC.md](./SPEC.md) § 5 (API Specification)

---

## Design System

**Colors** (defined in `frontend/src/styles/variables.css`):
- **Brand accent**: Orange (#FF7043) — primary color for buttons, active states, highlights, and logo wordmark
- **Text**:
  - Heading: #263238 (dark gray, 700+ weight for contrast)
  - Body/secondary: #546E7A (medium gray, regular weight)
  - On orange: #FFFFFF (white, for button text and light overlays)
- **Backgrounds**:
  - Page default: #FFFDF9 (warm off-white, very light cream)
  - Section alternate: #FAF3EB (warmer cream, for repeated blocks)
  - Neutral/disabled: #F3F4F6 (light gray, for inputs and inactive states)
  - Card: #FFFFFF (white, with soft shadow)
- **Category/macro tints** (60% opacity background + 700-weight dark text for badges and chips):
  - Protein/meals: #FFEDD5 background / #C2410C text
  - Water/hydration: #E0F2FE background / #0369A1 text
  - Weight/alerts: #FFE4E6 background / #BE123C text
- **Status**:
  - Error/validation: #D64444 (solid red, no tint)
  - Success: #2E7D32 (kept for compatibility with existing logic; refine to match accent if needed)
  - Info: #0369A1 (blue, from water tint)

**Typography**:
- Font family: Roboto, sans-serif (no serifs)
- Weight scale:
  - 400 (regular): body text, labels
  - 700 (bold): category chips, secondary labels
  - 800 (extra-bold): logo wordmark "Track" and "Intake"
- Sizing: Responsive; heading (H1) is 36px on desktop, scaled down on mobile

**Spacing** (8px grid, **unchanged from current**):
- xs=4px, sm=8px, md=16px, lg=24px, xl=32px

**Border radius**:
- Pill shapes (filter chips, circular avatars, FABs): `border-radius: 50%` / Tailwind `rounded-full`
- Card corners: `border-radius: 16px` / Tailwind `rounded-2xl`
- Card header top corners only: `border-radius: 12px 12px 0px 0px` / custom
- Form inputs: `border-radius: 8px` / Tailwind `rounded-sm`

**Shadows**:
- Card/lift effect: `0 2px 8px rgba(0, 0, 0, 0.08)` (soft, subtle)
- Hover/active elevation: `0 4px 12px rgba(0, 0, 0, 0.12)` (slightly darker/larger)
- Modal/overlay shadow: `0 8px 24px rgba(0, 0, 0, 0.15)` (deep shadow for overlays)
(These already exist in `variables.css` and can be kept unchanged.)

**Key component patterns**:
- **Logo/wordmark**: Bipartite: "Track" in bold orange (#FF7043), "Intake" in bold dark (#263238). No emoji or icon.
- **Floating action buttons**: Two fixed circular FABs (bottom-right corner), orange background, white icons, 32px diameter, soft shadow.
- **Filter/category pills**: Outlined (light gray #F3F4F6 background, dark text) when inactive; solid orange (#FF7043) background, white text when active. Rounded-full.
- **Stat cards**: Column layout, white background (#FFFFFF), rounded-2xl corners, soft shadow. Icon in orange-tinted chip (top-right), numeric value in orange accent, descriptive label in body gray.
- **Avatar**: Circular (rounded-full), orange background, white initials text (no photo).
- **Water/meal tracker**: Cards stacked, each with icon, macro breakdown, timestamp. Tinted category chip for the food/water type.
- **Section dividers**: Wavy SVG ornaments between major sections (decorative, not load-bearing for semantics).

**Design principles**:
- Warm, inviting aesthetic: cream backgrounds with orange accent create a friendly, approachable feel.
- Accessible contrast: heading #263238 on cream #FFFDF9 meets 4.5:1 WCAG AA standard; body text #546E7A on same background meets 3:1.
- Rounded, soft corners everywhere (no sharp edges): fosters trust and calm.
- Orange (#FF7043) as the single call-to-action color: all primary CTAs and active states use this to guide user attention.

**Related files**:
- `templates/base.html` — Tailwind CDN link, base layout
- `templates/dashboard.html` — Page styling, meal cards, macro chart
- `templates/login.html`, `templates/register.html` — Auth form styling

---

## High-Level Code Flow

### Voice Meal Ingestion (Core Feature)

```
User (Browser)
  ↓ 1. Click "Record Meal" on dashboard
AudioRecorder Component (static/js/audioRecorder.js)
  ↓ 2. Record voice → .wav file via MediaRecorder API
  ↓ 3. POST /meals/voice (multipart/form-data with Authorization header)
Backend: meals/views.py::CreateMealVoiceView
  ↓ 4. Validate audio (extension, size < 25MB)
  ↓ 5. Call create_meal_from_audio() service
  ↓ 6. Transcribe via NVIDIA Parakeet (meals/services/whisper_service.py)
  ↓ 7. Parse via Groq Llama-3.3-70B (meals/services/llm_service.py)
  ↓ 8. Validate macros via nutrition_service.validate_macros() (±10% tolerance)
  ↓ 9. Save Meal + MealItem records to PostgreSQL via Django ORM
  ↓ 10. Return 201 with meal JSON (id, items, totals, confidence_score)
Frontend: Dashboard.addMeal()
  ↓ 11. Update local meals array, re-render meal list
  ↓ 12. User can edit/delete/record another meal
```

**Validation Checkpoints**:
1. Audio format (mp3, wav, m4a, webm), size < 25MB
2. Whisper/Parakeet success (timeout 30s)
3. LLM JSON validity (all fields present, valid types)
4. Macro sanity (±10% tolerance on kcal calculation)
5. Confidence scoring (0.0-1.0 per item)

See [SPEC.md](./SPEC.md) § 8 (LLM Prompting) for Groq system prompt.

---

## Testing Strategy

### Backend (pytest + pytest-django)

- **Unit tests**: Each service function tested independently
- **Integration tests**: Auth flow, DB operations, API endpoints
- **Fixtures**: Fixtures in `tests/conftest.py` (test_user, test_user_with_google)
- **Mocking**: Mock Groq/NVIDIA responses to avoid API calls in tests
- **Coverage target**: >80%

**Example test**:
```python
import pytest
from django.test import Client

@pytest.mark.django_db
def test_voice_endpoint_valid_audio(test_user):
    """Test voice upload endpoint with valid audio."""
    from accounts.jwt import create_access_token
    client = Client()
    token = create_access_token({'user_id': test_user.id})
    
    with open("tests/fixtures/sample_meal.wav", "rb") as f:
        response = client.post(
            "/meals/voice",
            {'audio': f},
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )
    
    assert response.status_code == 201
    data = response.json()
    assert data['confidence_score'] > 0.7
```

### Google OAuth Testing

**Backend OAuth endpoint test**:
```python
import pytest
from unittest.mock import patch
from django.test import Client
from accounts.models import User

@pytest.mark.django_db
def test_google_login_new_user():
    """Test Google OAuth login creates new user."""
    mock_idinfo = {
        'sub': 'google_123',
        'email': 'user@gmail.com',
        'name': 'Test User'
    }
    
    client = Client()
    with patch('google.oauth2.id_token.verify_oauth2_token', return_value=mock_idinfo):
        response = client.post(
            '/auth/google',
            data={'id_token': 'mock_token'},
            content_type='application/json'
        )
    
    assert response.status_code == 200
    data = response.json()
    assert 'access_token' in data
    
    # Verify user created
    user = User.objects.get(email='user@gmail.com')
    assert user.google_id == 'google_123'

@pytest.mark.django_db
def test_google_login_existing_user():
    """Test Google OAuth login returns existing user."""
    user = User.objects.create_user(
        username='testuser',
        email='existing@gmail.com',
        google_id='google_456'
    )
    
    mock_idinfo = {
        'sub': 'google_456',
        'email': 'existing@gmail.com',
        'name': 'Existing User'
    }
    
    client = Client()
    with patch('google.oauth2.id_token.verify_oauth2_token', return_value=mock_idinfo):
        response = client.post(
            '/auth/google',
            data={'id_token': 'mock_token'},
            content_type='application/json'
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data['user_id'] == user.id

def test_google_login_invalid_token():
    """Test Google OAuth rejects invalid tokens."""
    client = Client()
    with patch('google.oauth2.id_token.verify_oauth2_token', side_effect=ValueError):
        response = client.post(
            '/auth/google',
            data={'id_token': 'invalid_token'},
            content_type='application/json'
        )
    
    assert response.status_code == 401
```

---

## Common Pitfalls & Debugging

### "Meal confidence score is too low"
- Check Groq Llama prompt (meals/services/llm_service.py)
- Vague transcripts ("I ate stuff") get low confidence
- Fallback: user can edit before saving

### "Macro calculations don't match"
- Groq might round differently; allow ±10% tolerance
- Check validation logic in meals/services/nutrition_service.py
- Log request/response for debugging

### "Audio upload fails"
- Check browser console (Dev Tools → Network tab)
- Verify Parakeet is configured (`NVIDIA_ASR_FUNCTION_ID` set, NVIDIA API key works)
- Non-WAV uploads (MP3, M4A, WebM) are automatically transcoded to WAV via pydub+ffmpeg
- If transcoding fails ("ffmpeg not found"), install ffmpeg or check audio format validity
- Test with curl: `curl -F "audio=@sample.wav" -H "Authorization: Bearer <jwt_token>" http://localhost:8000/meals/voice`

### "JWT token expired"
- Frontend: Auto-logout on 401 (static/js/apiClient.js interceptor)
- Check token in localStorage: `localStorage.getItem('access_token')`
- Login again to get fresh token (7-day expiry via accounts/jwt.py)

### "Cannot connect to PostgreSQL"
- Check Docker container is running: `docker ps | grep meal-postgres`
- Verify `DATABASE_URL` in `.env` matches container's port/name
- Test locally: `psql postgresql://postgres:postgres@localhost:5432/meal_system`
- Backend fails fast at startup with a connection error if DB is unreachable

### Google OAuth Troubleshooting

### "Google sign-in button not appearing"
- Check `GOOGLE_CLIENT_ID` is set in `.env`
- Verify Google Identity Services SDK loads in templates/login.html
- Check browser console (Dev Tools → Console) for errors
- Ensure Google script tag is present: `<script src="https://accounts.google.com/gsi/client" async defer></script>`

### "401 Invalid token from Google backend"
- Verify `GOOGLE_CLIENT_ID` in `.env` matches Google Cloud Console
- Ensure authorized redirect URIs include `http://localhost:8000/login`
- Test token verification: `python -c "from google.oauth2 import id_token; print('Import OK')"`

### "CORS error on /auth/google request"
- Django CORS is configured in meal_system/settings.py
- Ensure CORS_ALLOWED_ORIGINS includes localhost:8000
- Check browser Network tab for actual CORS headers

### "User created but not logging in consistently"
- Verify `google_id` is persisted in DB: `python manage.py dbshell` → `SELECT email, google_id FROM accounts_user;`
- Test lookup: `User.objects.get(email='test@example.com')`

### "Token still valid after logout"
- Frontend: Logout deletes token from localStorage (static/js/auth.js::logout())
- Django: Tokens are stateless; short expiry (7 days) and client-side deletion are sufficient

---

## Accessibility & Responsive Design

**Mobile-first approach**:
- Test at 375px (base mobile), 600px (tablet), 1024px (desktop)
- Touch targets: 44px minimum
- Text contrast: 4.5:1 (AA standard)

**Testing keyboard navigation**:
- Tab through all buttons/inputs in templates
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
python -m black meal_system/ accounts/ meals/
python -m flake8 meal_system/ accounts/ meals/
pytest
git log --oneline -n 5
```

---

## Production Build & Render.com Deployment

### Django Production

**Environment Setup**:
- `DEBUG=False` in `.env`
- `SECRET_KEY` must be a strong random string (generated on first setup)
- `DATABASE_URL` points to managed PostgreSQL (Render or external)
- All API keys set (GROQ, NVIDIA, Google)

**Collectstatic**:
```bash
python manage.py collectstatic --noinput
```

This bundles Tailwind CSS from CDN and vanilla JS into `static/` for WhiteNoise serving.

**Start Command**:
```bash
gunicorn meal_system.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2 --timeout 120
```

**Render Deployment**:
- See [RENDER_DEPLOYMENT.md](./RENDER_DEPLOYMENT.md) for full setup
- TL;DR: Push to GitHub → Render auto-deploys from `render.yaml` → Django at `https://meal-system.onrender.com`
- Render auto-creates PostgreSQL database and sets `DATABASE_URL`
- Build command includes `python manage.py migrate`

---

## Deployment Checklist (Pre-Sept 12)

**Django Backend**:
- [ ] `pip install -r requirements.txt` works (no missing packages)
- [ ] `python manage.py collectstatic --noinput` succeeds
- [ ] `python manage.py migrate` runs without errors
- [ ] `gunicorn meal_system.wsgi:application` starts without errors
- [ ] `.env.example` updated with all required keys (no secrets)
- [ ] DEBUG=False in production `.env`
- [ ] All API keys set (GROQ, NVIDIA, Google)
- [ ] PostgreSQL connection tested from production environment
- [ ] No print() / logging of sensitive data

**Templates & Frontend (Vanilla JS)**:
- [ ] All HTML templates render without errors
- [ ] JavaScript loads from `/static/js/` CDN or local
- [ ] Tailwind CSS loads from CDN
- [ ] Chart.js loads from CDN
- [ ] Google Sign-In button renders and is clickable
- [ ] Audio recorder works on dashboard
- [ ] No console errors in DevTools

**End-to-End**:
- [ ] Tests passing: `pytest`
- [ ] PostgreSQL and API services reachable from production environment
- [ ] README complete (setup instructions + Google OAuth steps)
- [ ] Django admin at `/admin` (optional, for data management)
- [ ] Google OAuth tested (token validation, user creation, existing user login)
- [ ] JWT tokens issued after OAuth login (7-day expiry)
- [ ] CORS configured (Django CORS middleware)
- [ ] Responsive on mobile (375px), tablet (600px), desktop (1024px+)
- [ ] Accessibility tested (keyboard nav, screen reader labels)
- [ ] Error messages user-friendly (not Django stack traces)
- [ ] Confidence badges working (green >90%, orange 70-90%, red <70%)
- [ ] Google Client ID/Secret configured in production environment
- [ ] Production redirect URI matches Google Cloud Console settings
- [ ] Logout clears token from localStorage
- [ ] Render.yaml configured with correct build/start commands
- [ ] GitHub repo connected to Render for auto-deploy
- [ ] PostgreSQL backups configured (Render auto-handles)

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
| Backend code | `meal_system/`, `accounts/`, `meals/` |
| Templates | `templates/` |
| Frontend JS | `static/js/` |
| Google OAuth setup | See "Google OAuth 2.0 Setup" above (§ this file) |
| Render deployment | [RENDER_DEPLOYMENT.md](./RENDER_DEPLOYMENT.md) |
| Google Cloud Console | https://console.cloud.google.com |
| google-auth library | https://github.com/googleapis/google-auth-library-python |
| Render.com | https://render.com |
| Django docs | https://docs.djangoproject.com |
| Django REST Framework | https://www.django-rest-framework.org |
| PostgreSQL | https://www.postgresql.org |

---

## Getting Help

1. **Setup issues**: Check README.md Quick Start section
2. **Code questions**: Review code files (well-structured, short)
3. **API questions**: Check meal_system/urls.py for routing
4. **Design questions**: See templates/ and static/css/
5. **Architecture questions**: This file + [SPEC.md](./SPEC.md)

# Dashboard Parity — Bring `docs/Dashboard.dc.html` mockup features into the live dashboard

**Purpose**: Implement missing features from the design mockup (`docs/Dashboard.dc.html`) into
the real dashboard (`templates/dashboard.html` and backend). The mockup shows a richer
TrackIntake experience with water tracking, health tools (BMI/weight), meal category filtering,
manual meal entry, a hero section with stat cards, personalized diet recommendations, a full
navbar with nav links + user avatar, and a footer. Currently, only the tabbed voice/text/photo AI
meal ingestion and daily macro summary exist.

This is an additive task: **the mockup's features are wired into the live app while preserving**
the existing Record/Type/Photo tabs, macro chart, confidence badges, date picker, and auth guard.

**Scope decisions** (user-confirmed):
- Water tracking + Weight logging: full-stack persistence (`health` Django app with models,
  migrations, API endpoints, serializers).
- BMI & Body-Fat calculators: stateless, client-side only (user inputs height/weight/measurements,
  gets instant result, no database).
- Diet Recommendations: static 3-card layout with hardcoded suggestions (no AI).
- Meal categories (Early-Morning/Breakfast/Mid-Morning/Lunch/Afternoon Snack/Dinner/Bedtime): new
  `meal_category` field on `Meal`, filterable server-side.
- Navbar & footer links: visual placeholders (`href="#"` or real routes where they exist); no new
  pages.
- Manual meal entry: new 4th "Manual" tab reusing the existing text-parsing pipeline (no new
  AI/LLM code).

---

## Before: Current State

**Live dashboard** (`templates/dashboard.html`):
- Minimal navbar: logo + Logout button only
- Date picker + 3 tabbed input panels:
  - 🎤 Record: voice recording → Parakeet ASR → Groq LLM macro parse
  - ⌨️ Type: free-text description → Groq LLM macro parse
  - 📷 Photo: image upload → Gemini 2.5-flash vision → Groq LLM macro parse
- Daily Summary: 5 stat cards (Calories, Protein, Carbs, Fats, Fiber) with orange accent + icon
  chips
- Macro Breakdown: Chart.js doughnut chart (Protein/Carbs/Fats %)
- Meals List: stacked cards with meal items, time, confidence badge, Delete button. No
  category grouping or filtering.
- No water tracking, no health tools, no diet recommendations, no footer, no hero section.

**Backend** (`meals/models.py`, `meals/views.py`, `meals/serializers.py`):
- `Meal` model: `user`, `original_text`, `transcription_text`, `confidence_score`,
  `input_method` (voice/text/image), `created_at`, `updated_at`.
- `MealItem` model: 10 nutrition fields (calories, protein, carbs, fats, fiber, etc.), indexed by
  meal.
- Views: `CreateMealVoiceView`, `CreateMealTextView`, `CreateMealImageView`, `DashboardView`,
  `MealDetailView` (PATCH/DELETE). All use DRF serializers, follow the `IsAuthenticated`
  + object-scoped query pattern.
- No water/weight models or endpoints.

**Authentication** (`accounts/models.py`, `accounts/views.py`):
- `User` model: email, username, google_id (nullable, unique).
- Auth endpoints: `/auth/register`, `/auth/login`, `/auth/google`. No user profile endpoint
  (e.g., GET `/auth/me` for navbar display).

**Frontend JS** (`static/js/`):
- `dashboard.js`: `Dashboard` class manages meal list, daily totals, rendering. Calls
  `apiGet`/`apiPost`/`apiPatch`/`apiDelete` from `apiClient.js`.
- `macroChart.js`: `MacroChart` class wraps Chart.js doughnut, renders empty/full states.
- `mealInputTabs.js`: tab switching for Record/Type/Photo.
- `audioRecorder.js`, `cameraCapture.js`: media capture for voice and photo.
- `formatting.js`: `formatNumber`, `formatTime`, `formatISO`, `formatDate`.
- `nutrition.js`: `calculateMacroPercentages`, `getMacroColor`, `getConfidenceTintClass`.

**Design tokens** (`templates/base.html`, Tailwind config):
- Colors: `brand-orange: #FF7043`, `heading: #263238`, `body: #546E7A`, `cream: #FFFDF9`,
  `cream-alt: #FAF3EB`, `error: #D64444`, `success: #2E7D32`.
- Shadows: `shadow-card: 0 2px 8px rgba(0,0,0,0.08)`, `shadow-hover: 0 4px 12px rgba(0,0,0,0.12)`,
  `shadow-modal: 0 8px 24px rgba(0,0,0,0.15)`.
- Radii: Tailwind `rounded-2xl` (16px), `rounded-full`, `rounded-lg` (8px).
- Font: Roboto 400/700/800, via Google Fonts CDN.

**Design mockup** (`docs/Dashboard.dc.html`, 318 lines):
- Navbar: bipartite "Track" (orange) + "Intake" (dark) logo, nav links (Home/Tools/Health/
  Diet/Progress/Blogs), user avatar + name display.
- Hero section: "Fuel your journey with smart nutrition" headline, 3 stat cards (Calories
  Today, Water Intake, Current Weight) with goals/subtotals, decorative stats graphic panel
  (SVG bar chart + circles).
- Add Meals (2-column grid):
  - Left: structured form (Food 1, Remark, Time picker, Category selector with pills
    "Early-Morning"/"Mid-Morning"/"Lunch"/"Afternoon Snack", "Log Meal"/"Delete" buttons).
  - Right: "Logged Meals" section with date picker, category filter pills (All/Early-Morning/
    Breakfast/Mid-Morning/Lunch/Afternoon Snack/Dinner/Bedtime, with counts), empty state.
- Water Intake Tracker: 10-glass visual, date picker, "⬆️ Add a Glass" button, "X of 10 glasses
  completed".
- Health Tools (3-column grid): Weight Tracker, BMI Calculator, Body-Fat Calculator (cards with
  emoji icons + descriptions).
- Personalized Diet Recommendations (3-column grid): Breakfast (Quinoa bowl), Lunch (Grilled
  salmon), Dinner (Chickpea stir-fry) with calorie/protein badges and "View Full Diet Plan →"
  button.
- Footer (3-column grid): brand blurb + social links, Quick Links (Dashboard/Appointments/
  Profile/Health), Legal (Privacy/Terms/Refund Policy/Contact), copyright bar.

---

## Current Architecture

### Backend

**`meal_system/settings.py`**:
- `INSTALLED_APPS` includes `'meals'`, `'accounts'`, `'rest_framework'`.
- Tailwind and Chart.js loaded via CDN in `templates/base.html`.
- JWT config: `JWT_ALGORITHM`, `JWT_EXPIRY_SECONDS`.

**`meal_system/urls.py`**:
- Routes: `/auth/*` → `accounts.urls`, `/meals/*` → `meals.urls`, `/` / `/login` / `/register`
  → templates.
- Context processor: `google_client_id` injected into all templates.

**`accounts/models.py`**:
- `User(AbstractUser)`: email (unique), google_id (nullable, unique), updated_at.

**`accounts/views.py`**:
- `RegisterView`, `LoginView`, `GoogleLoginView`: all POST, return JWT access_token + user_id.
- No GET endpoint for user profile (needed for navbar display).

**`accounts/urls.py`**:
- Paths: `register`, `login`, `google`.

**`meals/models.py`**:
- `Meal`: user, original_text, transcription_text, parsed_at, created_at, updated_at,
  confidence_score, input_method (Voice/Text/Image). Indexed on (user, -created_at).
- `MealItem`: meal (FK), item_name, quantity, unit, serving_size_grams, calories, protein_g,
  carbs_g, fats_g, fiber_g, confidence, source (llm_estimate / user_input), llm_generated.

**`meals/views.py`**:
- `CreateMealVoiceView`, `CreateMealTextView`, `CreateMealImageView`: POST, `IsAuthenticated`,
  return 201 + MealSerializer.
- `ListMealsView`: GET with ?date=YYYY-MM-DD, ?limit=N, returns MealSerializer[].
- `MealDetailView`: PATCH (replace items, recalc confidence), DELETE, with object-level auth
  check (meal.user == request.user).
- `DashboardView`: GET ?date=YYYY-MM-DD, returns {date, meals[], daily_totals{}, confidence_distribution{}}.

**`meals/serializers.py`**:
- `MealSerializer`: meal_id, original_text, transcription_text, confidence_score, confidence_badge,
  parsed_at, meal_items[], totals{}, created_at, input_method.
- `MealItemSerializer`: id, item_name, quantity, unit, serving_size_grams, calories, protein_g,
  carbs_g, fats_g, fiber_g, confidence, source.
- `MealItemCreateSerializer`: validation schema for meal item creation.
- `MealTextInputSerializer`, `MealUpdateSerializer`: request validation.

**`meals/services/meal_service.py`**:
- `get_user_meals(user, date=None, limit=None)`: returns list of Meal objects for user, filtered
  by date and limited.
- `create_meal_from_audio/text/image(user, ...)`: shared `_assemble_meal()` helper:
  1. Raw items from LLM (Groq parse_meal or Gemini vision).
  2. Validate via `validate_macros()`.
  3. Create Meal + MealItems, set confidence_score as avg of item confidences.
- `replace_meal_items(meal, payload_data)`: delete old items, create new ones, recalc confidence.
- Utility functions: `calculate_daily_totals()`, `calculate_confidence_distribution()`,
  `get_confidence_badge()`.

### Frontend

**`templates/base.html`**:
- Doctype, meta (charset, viewport), title block.
- Tailwind CDN + config (brand-orange, heading, body, cream colors, shadows, font).
- Chart.js CDN.
- Script loads: auth.js, apiClient.js, formatting.js, nutrition.js.
- `{% block content %}` + `{% block extra_scripts %}`.

**`templates/dashboard.html`**:
- Extends base.html.
- Navbar include: `{% include "partials/_navbar.html" with show_logout=True %}`.
- Main container (max-w-4xl, px-4 py-8).
- Date picker input (id=date-picker), value set via formatISO (today).
- Tabbed input UI (id=input-tabs):
  - 🎤 Record tab (panel-record): button #record-btn, status div.
  - ⌨️ Type tab (panel-type): textarea #type-textarea, submit #type-submit-btn, status div.
  - 📷 Photo tab (panel-photo): file input, dropzone, camera capture (video#photo-camera-video),
    preview, buttons.
- Daily Summary (id=daily-summary): grid populated by `dashboard.renderSummary()`.
- Macro Chart (id=macro-chart-canvas): Chart.js canvas.
- Meals List (id=meals-list): div populated by `dashboard.renderMealList()`.
- Event handlers: date-picker change, record button click, tab switching (mealInputTabs.js).
- Inline script block initializes Dashboard class, handles auth guard.

**`templates/partials/_navbar.html`**:
- Sticky navbar: brand logo (Track/Intake bipartite text), Logout button (if show_logout=True).
- Simple flex layout, centered or spaced-between.

**`static/js/dashboard.js`**:
- `class Dashboard`: constructor (init meals[], dailyTotals{}, selectedDate, macroChart, isLoading).
- `fetchDashboard()`: async GET /meals/dashboard?date={selectedDate}, updates state, calls render().
- `handleMealResult(meal)`: prepend meal to array, updateTotals(), render().
- `updateMeal(mealId, mealItems)`: PATCH /meals/{mealId}, update local array, render().
- `deleteMeal(mealId)`: DELETE /meals/{mealId}, remove from array, render().
- `updateTotals()`: loop meals[], sum nutrition values.
- `render()`: calls renderSummary(), renderMealList(), renderMacroChart().
- `renderSummary()`: build 5 stat cards (Calories/Protein/Carbs/Fats/Fiber) HTML, inject into
  #daily-summary.
- `renderMealList()`: build meal cards (item names, time, confidence badge, delete button) HTML,
  or "No meals" message, inject into #meals-list.
- `renderMacroChart()`: call macroChart.render(dailyTotals) or renderEmpty() if 0 calories.
- Alert helpers: showError(), showSuccess(), showProgress().

**`static/js/macroChart.js`**:
- `class MacroChart(canvasId)`: wraps Chart.js doughnut.
- `render(totals)`: compute macro percentages, update chart data + labels.
- `renderEmpty()`: show "No data" message.

**`static/js/mealInputTabs.js`**:
- `initMealInputTabs()`: attach click handlers to tab buttons (id=input-tabs > button.input-tab).
- On click: hide all panels, show target panel (#panel-record/type/photo), update aria-selected.

**`static/js/audioRecorder.js`**:
- `class AudioRecorder`: uses MediaRecorder API.
- `start()`: request microphone, begin recording.
- `stop()`: stop recording, create WAV blob.
- `uploadAndProcess(onProgress, onSuccess, onError)`: POST to /meals/voice (multipart), handle
  response.

**`static/js/cameraCapture.js`**:
- `class CameraCapture` or helpers: access camera stream, capture canvas frame, preview.

**`static/js/apiClient.js`**:
- `apiRequest(endpoint, {method, body, headers})`: fetch with JWT auth header, timeout, 401
  logout.
- `apiGet(endpoint)`: GET + JSON response.
- `apiPost(endpoint, body)`: POST + check response.ok, throw if not.
- `apiPatch(endpoint, body)`: PATCH.
- `apiDelete(endpoint)`: DELETE, return null if 204.
- `apiPostFile(endpoint, formData, timeoutMs)`: multipart POST (for audio/image files).

**`static/js/formatting.js`**:
- `formatNumber(n, decimals)`: round and format.
- `formatTime(isoString)`: human-readable time (e.g., "2:30 PM").
- `formatISO(date)`: YYYY-MM-DD.
- `formatDate(isoString)`: human-readable date.

**`static/js/nutrition.js`**:
- `calculateMacroPercentages(totals)`: return {protein%, carbs%, fats%}.
- `getMacroColor(macroType)`: return hex color for macro.
- `getConfidenceTintClass(score)`: return Tailwind class (bg-green/orange/red + text) based on
  score.

**`static/js/auth.js`**:
- `getToken()`: read from localStorage.access_token.
- `setToken(token)`: write to localStorage.
- `removeToken()`: delete from localStorage.
- `isTokenValid()`: check presence and decode expiry.
- `logout()`: removeToken(), redirect to /login.

---

## Target Architecture

### New Django App: `health/`

Mirrors the structure of `meals/` app (models, serializers, views, urls, admin, migration).

**`health/models.py`**:
```python
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator

class WaterLog(models.Model):
    """Track daily water intake (glasses per day)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='water_logs')
    date = models.DateField()  # YYYY-MM-DD
    glass_count = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(50)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'date')  # One entry per user per day
        ordering = ['-date']
        indexes = [models.Index(fields=['user', '-date'])]

class WeightEntry(models.Model):
    """Track user weight over time."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='weight_entries')
    weight_kg = models.FloatField(validators=[MinValueValidator(0)])  # in kilograms
    logged_at = models.DateTimeField()  # user-facing timestamp (can be backdated)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-logged_at']
        indexes = [models.Index(fields=['user', '-logged_at'])]
```

**`health/serializers.py`**:
```python
from rest_framework import serializers
from .models import WaterLog, WeightEntry

class WaterLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaterLog
        fields = ['id', 'date', 'glass_count', 'created_at', 'updated_at']

class WeightEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightEntry
        fields = ['id', 'weight_kg', 'logged_at', 'created_at', 'updated_at']

class WaterLogCreateUpdateSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)  # defaults to today if omitted
    glass_count = serializers.IntegerField(min_value=0, max_value=50)

class WeightEntryCreateSerializer(serializers.Serializer):
    weight_kg = serializers.FloatField(min_value=0)
    logged_at = serializers.DateTimeField(required=False)  # defaults to now() if omitted
```

**`health/views.py`**:
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime, date
from .models import WaterLog, WeightEntry
from .serializers import WaterLogSerializer, WeightEntrySerializer, WaterLogCreateUpdateSerializer, WeightEntryCreateSerializer

class WaterLogView(APIView):
    """GET/POST water intake for a given date (default: today)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ?date=YYYY-MM-DD (optional, default today)
        date_str = request.query_params.get('date')
        if not date_str:
            target_date = date.today()
        else:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'detail': 'date must be YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Deny-by-default: filter by user
        water_log = WaterLog.objects.filter(user=request.user, date=target_date).first()
        if not water_log:
            return Response({'glass_count': 0, 'date': target_date.isoformat()}, status=status.HTTP_200_OK)
        
        serializer = WaterLogSerializer(water_log)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # upsert: update or create for today (or specified date)
        serializer = WaterLogCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'detail': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        target_date = serializer.validated_data.get('date') or date.today()
        glass_count = serializer.validated_data['glass_count']
        
        water_log, created = WaterLog.objects.update_or_create(
            user=request.user,
            date=target_date,
            defaults={'glass_count': glass_count}
        )
        
        response_serializer = WaterLogSerializer(water_log)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class WeightLogView(APIView):
    """GET recent weight entries, POST a new weight entry."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ?limit=10 (default 10, most recent)
        limit = int(request.query_params.get('limit', 10))
        limit = max(1, min(limit, 100))  # clamp to [1, 100]
        
        # Deny-by-default: filter by user
        entries = WeightEntry.objects.filter(user=request.user).order_by('-logged_at')[:limit]
        serializer = WeightEntrySerializer(entries, many=True)
        return Response({'entries': serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = WeightEntryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'detail': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        weight_kg = serializer.validated_data['weight_kg']
        logged_at = serializer.validated_data.get('logged_at') or timezone.now()
        
        entry = WeightEntry.objects.create(
            user=request.user,
            weight_kg=weight_kg,
            logged_at=logged_at
        )
        
        response_serializer = WeightEntrySerializer(entry)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
```

**`health/urls.py`**:
```python
from django.urls import path
from . import views

urlpatterns = [
    path('water', views.WaterLogView.as_view(), name='water_log'),
    path('weight', views.WeightLogView.as_view(), name='weight_log'),
]
```

**`health/admin.py`**:
```python
from django.contrib import admin
from .models import WaterLog, WeightEntry

@admin.register(WaterLog)
class WaterLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'glass_count')
    list_filter = ('date',)
    search_fields = ('user__email',)

@admin.register(WeightEntry)
class WeightEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'weight_kg', 'logged_at')
    list_filter = ('logged_at',)
    search_fields = ('user__email',)
```

**`health/migrations/0001_initial.py`**: auto-generated via `python manage.py makemigrations health`.

### Update Django Config

**`meal_system/settings.py`**:
- Add `'health'` to `INSTALLED_APPS`.

**`meal_system/urls.py`**:
- Add `path('health/', include('health.urls'))`.

### Update `accounts/` for User Profile Endpoint

**`accounts/views.py`** (add):
```python
class MeView(APIView):
    """GET current user's profile."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        return Response({
            'user_id': str(user.id),
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
        }, status=status.HTTP_200_OK)
```

**`accounts/urls.py`** (update):
```python
urlpatterns = [
    path('register', views.RegisterView.as_view(), name='register'),
    path('login', views.LoginView.as_view(), name='login'),
    path('google', views.GoogleLoginView.as_view(), name='google_login'),
    path('me', views.MeView.as_view(), name='me'),
]
```

### Update `meals/` for Meal Categories

**`meals/models.py`** (update `Meal`):
```python
class Meal(models.Model):
    INPUT_METHOD_CHOICES = [('voice', 'Voice'), ('text', 'Text'), ('image', 'Image')]
    MEAL_CATEGORY_CHOICES = [
        ('early_morning', 'Early Morning'),
        ('breakfast', 'Breakfast'),
        ('mid_morning', 'Mid-Morning'),
        ('lunch', 'Lunch'),
        ('afternoon_snack', 'Afternoon Snack'),
        ('dinner', 'Dinner'),
        ('bedtime', 'Bedtime'),
    ]
    
    # ... existing fields ...
    input_method = models.CharField(max_length=10, choices=INPUT_METHOD_CHOICES, default='voice')
    meal_category = models.CharField(
        max_length=20,
        choices=MEAL_CATEGORY_CHOICES,
        default='lunch',  # fallback; derived from created_at time if not supplied
    )
    
    # ... rest of model ...
```

**`meals/serializers.py`** (update):
- Add `meal_category` to `MealSerializer` fields.
- Add `meal_category` to `MealItemCreateSerializer` (optional, default 'lunch').
- Add `meal_category` to `MealTextInputSerializer`, `MealUpdateSerializer` (optional).

**`meals/services/meal_service.py`** (update):
- `get_user_meals(user, date=None, limit=None, category=None)`: add optional category filter.
- `_assemble_meal(...)`: add `meal_category` param, pass to `Meal.objects.create()`.
- `create_meal_from_audio/text/image(user, ...)`: add optional `category` param, pass to
  `_assemble_meal()`.
- **Helper function** to auto-derive category from `created_at` time (if not supplied):
  ```python
  def derive_meal_category_from_time(dt):
      hour = dt.hour
      if 5 <= hour < 7: return 'early_morning'
      elif 7 <= hour < 10: return 'breakfast'
      elif 10 <= hour < 12: return 'mid_morning'
      elif 12 <= hour < 14: return 'lunch'
      elif 14 <= hour < 17: return 'afternoon_snack'
      elif 17 <= hour < 21: return 'dinner'
      else: return 'bedtime'  # 21:00 - 5:00
  ```

**`meals/views.py`** (update):
- `CreateMealVoiceView`, `CreateMealTextView`, `CreateMealImageView`: read optional `category`
  from request (POST body or query param), pass to `create_meal_from_*()`.
- `DashboardView` (GET /meals/dashboard?date=&category=): return per-category counts in
  response under a new `category_counts` field:
  ```json
  {
    "date": "2026-09-11",
    "meals": [...],
    "daily_totals": {...},
    "category_counts": {
      "early_morning": 0,
      "breakfast": 2,
      "lunch": 1,
      ...
    }
  }
  ```
- `ListMealsView` (GET /meals?date=&category=): filter by category if supplied.

### Update Frontend: Templates

**`templates/partials/_navbar.html`** (replace):
```html
<nav class="sticky top-0 z-10 bg-white border-b border-gray-200 shadow-sm">
  <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
    <!-- Logo -->
    <a href="/" class="flex items-center">
      <span class="text-3xl font-extrabold tracking-tight text-brand-orange">Track</span><span class="text-3xl font-extrabold tracking-tight text-heading">Intake</span>
    </a>
    
    <!-- Nav Links (placeholder) -->
    <nav class="hidden md:flex gap-8">
      <a href="#" class="text-sm text-body hover:text-heading">Home</a>
      <a href="#" class="text-sm text-body hover:text-heading">Tools</a>
      <a href="#" class="text-sm text-body hover:text-heading">Health</a>
      <a href="#" class="text-sm text-body hover:text-heading">Diet</a>
      <a href="#" class="text-sm text-body hover:text-heading">Progress</a>
      <a href="#" class="text-sm text-body hover:text-heading">Blogs</a>
    </nav>
    
    <!-- User + Logout -->
    {% if show_logout %}
    <div class="flex items-center gap-3">
      <div id="user-avatar" class="w-8 h-8 bg-brand-orange rounded-full flex items-center justify-center text-white text-xs font-bold">?</div>
      <span id="user-name" class="text-sm text-body hidden sm:inline">User</span>
      <button onclick="logout()" class="text-sm font-medium text-body hover:text-heading">Logout</button>
    </div>
    {% endif %}
  </div>
</nav>

<script>
  // Fetch and display user info
  if (document.getElementById('user-avatar')) {
    apiGet('/auth/me')
      .then(data => {
        document.getElementById('user-avatar').textContent = (data.email || data.username || '?')[0].toUpperCase();
        document.getElementById('user-name').textContent = data.username || data.email || 'User';
      })
      .catch(err => console.error('Failed to fetch user info:', err));
  }
</script>
```

**`templates/dashboard.html`** (update and add sections):
- Keep existing: date-picker, input-tabs (Record/Type/Photo), daily-summary, macro-chart-canvas,
  meals-list.
- **Add new "Manual" tab** to input-tabs (4th button):
  ```html
  <button type="button" role="tab" id="tab-manual" aria-controls="panel-manual" aria-selected="false" tabindex="-1"
    class="input-tab px-4 py-3 min-h-11 font-medium text-sm border-b-2 border-transparent text-body hover:text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2 rounded-t"
    data-target="manual">✍️ Manual</button>
  
  <!-- Manual Panel -->
  <div id="panel-manual" role="tabpanel" aria-labelledby="tab-manual" class="input-panel hidden">
    <div class="space-y-4">
      <div>
        <label for="manual-food-name" class="block text-sm font-medium text-heading mb-2">Food Name</label>
        <input id="manual-food-name" type="text" placeholder="e.g. Chicken breast" maxlength="255"
          class="w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2" />
      </div>
      <div>
        <label for="manual-remark" class="block text-sm font-medium text-heading mb-2">Remark (optional)</label>
        <input id="manual-remark" type="text" placeholder="e.g. grilled with olive oil" maxlength="255"
          class="w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2" />
      </div>
      <div>
        <label for="manual-category" class="block text-sm font-medium text-heading mb-2">Meal Category</label>
        <select id="manual-category" class="w-full px-4 py-3 border border-gray-300 rounded-lg text-heading focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2">
          <option value="early_morning">Early Morning</option>
          <option value="breakfast">Breakfast</option>
          <option value="mid_morning">Mid-Morning</option>
          <option value="lunch" selected>Lunch</option>
          <option value="afternoon_snack">Afternoon Snack</option>
          <option value="dinner">Dinner</option>
          <option value="bedtime">Bedtime</option>
        </select>
      </div>
      <div class="flex items-center justify-between">
        <div id="manual-status" class="text-sm text-body"></div>
        <button id="manual-submit-btn" type="button"
          class="px-6 py-3 min-h-11 bg-brand-orange text-white font-medium rounded-full shadow-card hover:shadow-hover hover:brightness-95 transition-all focus:outline-none focus:ring-2 focus:ring-brand-orange focus:ring-offset-2">
          Log Meal
        </button>
      </div>
    </div>
  </div>
  ```
  
- **Add Hero Section** (before date-picker):
  ```html
  <div class="bg-white rounded-2xl shadow-card p-8 mb-8">
    <div class="max-w-2xl">
      <h1 class="text-3xl font-bold text-heading mb-2">Fuel your journey with <span class="text-brand-orange">smart nutrition</span></h1>
      <p class="text-body mb-6">Log, learn, and stay ahead of your health goals every day.</p>
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-cream rounded-lg p-4 text-center">
          <p class="text-xs text-body mb-2">🔥 Calories Today</p>
          <p class="text-2xl font-bold text-brand-orange" id="hero-calories">0</p>
          <p class="text-xs text-body mt-1">kcal</p>
        </div>
        <div class="bg-cream rounded-lg p-4 text-center">
          <p class="text-xs text-body mb-2">💧 Water Intake</p>
          <p class="text-2xl font-bold text-brand-orange" id="hero-water">0</p>
          <p class="text-xs text-body mt-1">glasses</p>
        </div>
        <div class="bg-cream rounded-lg p-4 text-center">
          <p class="text-xs text-body mb-2">⚖️ Current Weight</p>
          <p class="text-2xl font-bold text-brand-orange" id="hero-weight">-</p>
          <p class="text-xs text-body mt-1">kg</p>
        </div>
      </div>
    </div>
  </div>
  ```
  
- **Add Water Tracker Section** (after meals-list):
  ```html
  <div class="mb-8">
    <h2 class="text-lg font-semibold text-heading mb-4">Water Intake Tracker 💧</h2>
    <div class="bg-white rounded-2xl shadow-card p-6 text-center">
      <input type="date" id="water-date-picker" class="border-none text-sm text-body font-medium focus:outline-none mb-6" />
      <div id="water-glasses-visual" class="flex justify-center gap-2 mb-4 flex-wrap"></div>
      <p id="water-status" class="text-sm text-body mb-4">0 of 10 glasses completed</p>
      <button id="water-add-btn" type="button" class="px-4 py-2 bg-brand-orange text-white font-medium rounded-full text-sm">⬆️ Add a Glass</button>
    </div>
  </div>
  ```
  
- **Add Health Tools Section** (after water tracker):
  ```html
  <div class="mb-8">
    <h2 class="text-lg font-semibold text-heading mb-4">Health Tools</h2>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <div class="bg-white rounded-2xl shadow-card p-6 text-center">
        <div class="text-3xl mb-3">⚖️</div>
        <h3 class="font-semibold text-heading mb-2">Weight Tracker</h3>
        <p class="text-xs text-body mb-4">Log your current weight</p>
        <button class="text-sm text-brand-orange font-medium">Add Weight</button>
      </div>
      <div class="bg-white rounded-2xl shadow-card p-6 text-center">
        <div class="text-3xl mb-3">📏</div>
        <h3 class="font-semibold text-heading mb-2">BMI Calculator</h3>
        <p class="text-xs text-body mb-4">Calculate your Body Mass Index</p>
        <button id="bmi-calculator-btn" class="text-sm text-brand-orange font-medium">Calculate BMI</button>
      </div>
      <div class="bg-white rounded-2xl shadow-card p-6 text-center">
        <div class="text-3xl mb-3">💪</div>
        <h3 class="font-semibold text-heading mb-2">Body Fat %</h3>
        <p class="text-xs text-body mb-4">Estimate body fat percentage</p>
        <button id="bodyfat-calculator-btn" class="text-sm text-brand-orange font-medium">Calculate</button>
      </div>
    </div>
    <!-- BMI Modal -->
    <div id="bmi-modal" class="hidden fixed inset-0 bg-black/50 flex items-center justify-center p-4">
      <div class="bg-white rounded-2xl shadow-modal p-6 max-w-sm w-full">
        <h3 class="text-lg font-semibold text-heading mb-4">BMI Calculator</h3>
        <div class="space-y-4">
          <div>
            <label for="bmi-height" class="block text-sm text-heading mb-2">Height (cm)</label>
            <input id="bmi-height" type="number" placeholder="170" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-orange" />
          </div>
          <div>
            <label for="bmi-weight" class="block text-sm text-heading mb-2">Weight (kg)</label>
            <input id="bmi-weight" type="number" placeholder="70" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-orange" />
          </div>
          <p id="bmi-result" class="text-center font-semibold text-brand-orange text-lg"></p>
          <div class="flex gap-2">
            <button onclick="document.getElementById('bmi-modal').classList.add('hidden')" class="flex-1 px-4 py-2 text-heading border border-gray-300 rounded-lg font-medium">Close</button>
            <button id="bmi-calculate-btn" class="flex-1 px-4 py-2 bg-brand-orange text-white rounded-lg font-medium">Calculate</button>
          </div>
        </div>
      </div>
    </div>
    <!-- Body Fat Modal (similar structure) -->
  </div>
  ```
  
- **Add Diet Recommendations Section** (after health tools):
  ```html
  <div class="mb-8">
    <h2 class="text-lg font-semibold text-heading mb-4">Personalized Diet Recommendations</h2>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <div class="bg-white rounded-2xl shadow-card overflow-hidden">
        <div class="bg-gradient-to-br from-orange-100 to-orange-50 h-32 flex items-center justify-center font-bold text-heading">Breakfast</div>
        <div class="p-4">
          <h3 class="font-semibold text-heading mb-1">Quinoa Bowl</h3>
          <p class="text-xs text-body mb-3">Fresh berries & nuts</p>
          <div class="flex justify-between text-xs">
            <span class="text-brand-orange font-medium">320 kcal</span>
            <span class="text-brand-orange font-medium">25g protein</span>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-2xl shadow-card overflow-hidden">
        <div class="bg-gradient-to-br from-orange-200 to-orange-100 h-32 flex items-center justify-center font-bold text-heading">Lunch</div>
        <div class="p-4">
          <h3 class="font-semibold text-heading mb-1">Grilled Salmon</h3>
          <p class="text-xs text-body mb-3">Roasted vegetables</p>
          <div class="flex justify-between text-xs">
            <span class="text-brand-orange font-medium">450 kcal</span>
            <span class="text-brand-orange font-medium">35g protein</span>
          </div>
        </div>
      </div>
      <div class="bg-white rounded-2xl shadow-card overflow-hidden">
        <div class="bg-gradient-to-br from-yellow-100 to-yellow-50 h-32 flex items-center justify-center font-bold text-heading">Dinner</div>
        <div class="p-4">
          <h3 class="font-semibold text-heading mb-1">Chickpea Stir-fry</h3>
          <p class="text-xs text-body mb-3">Mixed vegetables</p>
          <div class="flex justify-between text-xs">
            <span class="text-brand-orange font-medium">380 kcal</span>
            <span class="text-brand-orange font-medium">18g protein</span>
          </div>
        </div>
      </div>
    </div>
    <div class="text-center mt-6">
      <button class="px-6 py-3 bg-brand-orange text-white font-medium rounded-full text-sm">View Full Diet Plan →</button>
    </div>
  </div>
  ```

- **Add Footer** (at end, after main closing tag):
  ```html
  <footer class="bg-white border-t border-gray-200 mt-12">
    <div class="max-w-6xl mx-auto px-4 py-12">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-8 mb-8">
        <div>
          <div class="text-lg font-bold mb-4"><span class="text-brand-orange">Track</span><span class="text-heading">Intake</span></div>
          <p class="text-xs text-body mb-4">Your smart companion for everyday healthy eating — log meals, track water, and more.</p>
          <div class="flex gap-3">
            <a href="#" class="text-body text-sm hover:text-heading">f</a>
            <a href="#" class="text-body text-sm hover:text-heading">𝕏</a>
            <a href="#" class="text-body text-sm hover:text-heading">in</a>
          </div>
        </div>
        <div>
          <h3 class="font-semibold text-heading mb-4">Quick Links</h3>
          <ul class="space-y-2 text-xs">
            <li><a href="#" class="text-body hover:text-heading">Dashboard</a></li>
            <li><a href="#" class="text-body hover:text-heading">Appointments</a></li>
            <li><a href="#" class="text-body hover:text-heading">Profile</a></li>
            <li><a href="#" class="text-body hover:text-heading">Health</a></li>
          </ul>
        </div>
        <div>
          <h3 class="font-semibold text-heading mb-4">Legal</h3>
          <ul class="space-y-2 text-xs">
            <li><a href="#" class="text-body hover:text-heading">Privacy Policy</a></li>
            <li><a href="#" class="text-body hover:text-heading">Terms & Conditions</a></li>
            <li><a href="#" class="text-body hover:text-heading">Refund Policy</a></li>
            <li><a href="#" class="text-body hover:text-heading">Contact</a></li>
          </ul>
        </div>
      </div>
      <div class="text-center border-t border-gray-200 pt-8">
        <p class="text-xs text-body">© 2026 TrackIntake. All rights reserved. Made with ❤️</p>
      </div>
    </div>
  </footer>
  ```

### Add New Frontend JS Files

**`static/js/waterTracker.js`**:
- `class WaterTracker`: manage water intake for selected date.
- `fetchWaterLog(date)`: GET `/health/water?date={date}`.
- `addGlass(date)`: POST to `/health/water` with `{date, glass_count: current + 1}`.
- `renderWaterVisual()`: display 10 glass boxes, fill based on count.
- Wire up: #water-date-picker change event, #water-add-btn click event, #water-glasses-visual
  + #water-status update.

**`static/js/healthTools.js`**:
- Client-side calculators (no API calls).
- `calculateBMI(heightCm, weightKg)`: return number and category (underweight/normal/overweight/obese).
- `calculateBodyFat(heightCm, neckCm, waistCm, hipCm, gender)`: return % via US Navy formula.
- Wire up: modal open/close, input handlers, result display.

**`static/js/dietRecommendations.js`**:
- Static content, no fetch. Initialize on page load.
- Optional: wire up "View Full Diet Plan" button to `#` (placeholder).

### Update Existing `dashboard.js`

- Initialize WaterTracker class.
- Update `renderSummary()` to also populate #hero-calories, #hero-water (via waterTracker state),
  #hero-weight (via latest weight entry from health API).
- Add `?category=` filter to `fetchDashboard()` call and render category pills in meals list.

### Update Existing `mealInputTabs.js`

- Extend tab-switching logic to include new "Manual" tab.
- Add click handler to #manual-submit-btn to call `/meals/text` with concatenated text
  + category param.

---

## Rules You Must Preserve

1. **Do not touch Record/Type/Photo tabs** or their dependencies (`audioRecorder.js`,
   `cameraCapture.js`, `mealInputTabs.js` tab-switching logic). These tabs are the app's core
   feature and must work exactly as they do today.

2. **Keep Daily Summary cards and macro chart unchanged**. The hero section has different stat
   cards; the existing Daily Summary and Chart.js doughnut stay exactly as they are.

3. **Maintain backward compatibility**. All existing API routes (`/meals/voice`, `/meals/text`,
   `/meals/image`, `/meals/`, `/meals/{id}`, `/meals/dashboard`) must continue to work with
   their current request/response shapes. New fields (`meal_category`, `category_counts`) are
   *additive* (append-only, never change existing field names or remove fields).

4. **Follow security rules** (`.claude/rules/security.md` § 2: "Deny by default"):
   - Every new endpoint requires `IsAuthenticated` + object-level authorization (filter by
     `request.user`).
   - Validate all inputs via DRF serializers (min/max value checks, type coercion).
   - Use parameterized queries / ORM filtering, never string concatenation.
   - No mass assignment: explicitly whitelist fields in serializers.

5. **Use project design tokens**, not mockup's raw hex/fonts. Mockup uses `#ff6b35` (orange),
   `#263238` (heading), `#546E7A` (body text), etc. — the project's Tailwind config already has
   `brand-orange: #FF7043`, `heading: #263238`, `body: #546E7A`. Use Tailwind classes and
   existing shadows/radii. Do not copy inline `style=` attributes from the mockup.

6. **New `health` app must follow `meals` app patterns**:
   - Models with `user` FK + index on (user, date/logged_at).
   - Views with `IsAuthenticated` + filter by user.
   - Serializers for validation.
   - admin.py registration.
   - urls.py routing.
   - Migration auto-generated and committed.

7. **Preserve existing file structure**. Do not rename or move `templates/dashboard.html`,
   `static/js/dashboard.js`, `meals/models.py`, etc. Add new files (new health app, new JS
   classes) without deleting or renaming existing ones.

---

## Known Pitfalls

1. **`Meal.created_at` is `auto_now_add`** (non-editable): the mockup's manual-entry time picker
   is decorative. Logged meal times are always "now." Document this in the Manual tab UI
   ("Time is set to now when you submit").

2. **Water/Weight uniqueness**: `WaterLog` has `unique_together = ('user', 'date')`. When the
   user "adds a glass," upsert (update or create), don't insert duplicates. `WeightEntry` has
   no uniqueness constraint (users can log multiple weights on the same day); new entries are
   always appended.

3. **Category counts must be server-side**: the dashboard endpoint should compute and return
   per-category counts (e.g., `{breakfast: 2, lunch: 1, ...}`) so the frontend can render filter
   pills without a second API call. Compute these in the `DashboardView` GET handler.

4. **New `health` app in `INSTALLED_APPS`**: if you forget to add `'health'` to `INSTALLED_APPS`
   in `settings.py`, or forget to run `migrate`, Django will 500 with `no such table: health_waterlog`.

5. **Meal category auto-derivation**: when a meal is created via voice/text/image without an
   explicit `category` param, auto-derive it from the `created_at` hour (see helper function
   above). This way, meals logged at 7 AM default to "breakfast," meals at 12 PM to "lunch,"
   etc. Users can still override via manual tab or a future "edit category" flow.

6. **Hero section stat cards are display-only** (derived from dashboard state, not editable
   inputs). They update when the dashboard re-fetches.

7. **Placeholder nav links**: the navbar now has (Home/Tools/Health/Diet/Progress/Blogs) links
   with `href="#"`. They won't navigate anywhere. If real pages are built later, update the
   hrefs. For now, they're visual scaffolding.

---

## Testing & Verification Checklist

- [ ] **Migrations**: `python manage.py makemigrations health`, `python manage.py migrate` —
  both run cleanly with no conflicts. No errors on `python manage.py runserver` startup.

- [ ] **New health endpoints**: 
  - `GET /health/water?date=2026-09-11` → 200, returns water log.
  - `POST /health/water` with `{date, glass_count}` → 201/200 (upsert).
  - `GET /health/weight?limit=10` → 200, returns recent entries.
  - `POST /health/weight` with `{weight_kg, logged_at}` → 201.
  - `GET /auth/me` → 200, returns user profile (username, email).

- [ ] **Meal categories**:
  - Create meal via `/meals/text` with optional `?category=breakfast` → meal saved with that
    category, or auto-derived if omitted.
  - `GET /meals/dashboard?date=2026-09-11` → response includes `category_counts{...}` field
    with per-category counts.
  - Meal detail serializes `meal_category` field.

- [ ] **Frontend**:
  - Record/Type/Photo tabs still work (voice record, text submit, photo upload/camera).
  - Daily Summary cards and macro chart render unchanged.
  - Manual tab: fill food name + remark + category → click "Log Meal" → calls `/meals/text` →
    meal appears in list with correct category.
  - Water tracker: "Add a Glass" increments count via `/health/water` upsert.
  - BMI/Body-Fat modals: enter values → compute + display result instantly (no API call).
  - Hero stat cards: display calories, water count, last weight logged.
  - Navbar: logo + nav links (placeholder) + user avatar (initials) + display name + Logout.
  - Footer: visible and clickable (links go to #).
  - Responsive at 375px (mobile), 600px (tablet), 1024px (desktop).

- [ ] **Security**:
  - `/health/water?date=...` filters by `request.user` (deny-by-default).
  - Unauthenticated requests to new endpoints return 401.
  - Input validation: glass_count 0-50, weight_kg > 0, height in cm range, etc.
  - No SQL injection, no mass assignment, no IDOR.

- [ ] **Backward compatibility**:
  - Existing `/meals/*` endpoints still return same response shapes.
  - Existing template routes (`/`, `/login`, `/register`) unchanged.
  - Old clients (without `meal_category` field) can still create/fetch meals.

- [ ] **Code quality**:
  - No console errors (browser DevTools).
  - No 500 errors in server logs.
  - `pytest` passes (existing + new tests for health endpoints, meal categories).

---

## Sources & References

- **Mockup design**: `docs/Dashboard.dc.html` (318 lines, static HTML with inline styles).
- **Format reference**: `docs/design-system-website-sync-prompt.md` (structure: Purpose → Before/After
  → Architecture → Target → Rules → Pitfalls → Checklist).
- **Current codebase files**:
  - Backend: `meal_system/settings.py`, `meal_system/urls.py`, `accounts/`, `meals/`.
  - Frontend: `templates/base.html`, `templates/dashboard.html`, `templates/partials/`,
    `static/js/`.
  - Design tokens: Tailwind config in `templates/base.html`.
  - Security rules: `.claude/rules/security.md`.
  - Architecture docs: `CLAUDE.md` (entire file).

---

## Summary

This prompt brings the richer TrackIntake dashboard mockup into the live app by adding:
1. New `health` Django app for water + weight persistence.
2. Client-side BMI/Body-Fat calculators.
3. Meal category field + filtering.
4. Manual meal entry tab (reusing text-parse pipeline).
5. Navbar extensions (nav links, user avatar/name).
6. Hero section with stat cards.
7. Water tracker UI + logic.
8. Health tools section (cards + modals).
9. Static diet recommendations.
10. Footer with placeholder links.

All changes are *additive* and preserve existing Record/Type/Photo tabs, macro chart, and daily
summary. Security and backward compatibility are maintained via schema validation, object-scoped
queries, and careful API design. A fresh Claude Code session should execute this without further
user input, armed with the 4 scope decisions stated up front.

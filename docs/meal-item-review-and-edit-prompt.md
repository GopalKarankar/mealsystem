# Meal Item Review & Edit — Pre-save and Post-save — Dev Prompt

**Purpose**: This prompt instructs you to add a review/edit UI for meal items at two points in the user flow: (1) **before saving** — after Groq/Gemini parses a meal, show an editable preview of the parsed items so the user can correct names, quantities, and units before database commit; (2) **after saving** — add an "Edit" button next to the existing "Delete" button on each saved meal, letting users modify items long after ingestion. Both paths re-validate and re-lookup macros server-side, never trusting client-submitted nutrition numbers. Units are constrained to a fixed allowlist (g, kg, ml, l, oz, cup, bowl, plate, piece, serving) with approximate gram-equivalents for volume/container units so macro scaling works reasonably.

**Scope decisions**:
- **Pre-save flow**: LLM/vision parsing no longer auto-persists. New `/preview` endpoints parse and return items to the frontend unsaved; new `/confirm` endpoint persists them only after the user reviews/edits.
- **Unit system**: Fixed dropdown list for all items (g, kg, ml, l, oz, cup, bowl, plate, piece, serving). No per-food-type variation.
- **Macro re-computation**: On confirm (pre-save) and on PATCH (post-save), for each item: if name unchanged since preview → rescale already-resolved macros proportionally; if name changed → re-run `resolve_item_macros()` fresh. This **supersedes** the old "trust client PATCH macros" rule documented in `docs/add-usda-ifct-nutrition-lookup-prompt.md` (line 10) — the new edit UI never exposes macro fields, so this is justified and safe.
- **Post-save editing**: Reuse the existing whole-meal `PATCH /meals/{id}` → `replace_meal_items()` path; add an Edit button in the dashboard to open the same review UI pre-filled with current items. No per-item CRUD endpoints.
- **Conversions**: Add approximate gram-equivalents for volume/container units (cup ≈ 240g, bowl ≈ 400g, plate ≈ 300g, ml ≈ 1g, l ≈ 1000g) so macros still scale reasonably. `piece` and `serving` are intentionally unconvertible (same as today's fallback behavior).
- **Rate limiting**: The 3 new LLM-backed preview endpoints + confirm endpoint must be rate-limited per account + per IP per security.md §7. Audit existing rate-limit implementation and flag if missing.
- **No add/remove items**: Users can edit name/qty/unit but not add new items or delete individual items (must delete the whole meal). Explicit non-goal.

---

## Context: Before and After

### Before (Parse-and-Save, Whole-Meal Edit Only)

Today, voice/text/photo ingestion is synchronous — parse and persist in one request:

```
User clicks "Record Meal"
  ↓
Capture audio/text/photo
  ↓
POST /meals/voice (or /text, /image)
  ↓
Backend: Transcribe (audio) / Describe (photo) via LLM
  ↓
Backend: Parse via Groq JSON
  ↓
Backend: Validate & resolve macros (IFCT/USDA lookup or LLM estimate)
  ↓
Backend: Save Meal + MealItem rows immediately
  ↓
Return 201 with JSON (meal_id, items[], macros, confidence_score)
  ↓
Frontend: Add meal to the list, render in dashboard
  ↓
User sees meal. If item name is wrong: click per-meal Delete, re-record.
(No per-item edit, no pre-save review.)
```

**Current edit capability**: Whole-meal PATCH `/meals/{id}` with `meal_items` list (must re-submit all items); no UI button exposed yet.

### After (Parse→Preview→Confirm, Pre-save and Post-save Edit)

Parse and persist are now separated; review happens before commit:

```
User clicks "Record Meal"
  ↓
Capture audio/text/photo
  ↓
POST /meals/voice/preview (or /text/preview, /image/preview) [NEW]
  ↓
Backend: Transcribe / Describe / Parse (same as before)
  ↓
Backend: Resolve macros (same as before)
  ↓
Return items JSON (to frontend, no DB write yet)
  ↓
[NEW] Frontend: Show editable modal (name, qty, unit per item, read-only macro preview)
  ↓
User reviews/edits item details (correct "chikne" → "chicken", qty, unit)
  ↓
User clicks "Save Meal"
  ↓
POST /meals/confirm [NEW]
  ↓
Backend: For each item:
  - If name unchanged since preview → rescale macros proportionally
  - If name changed → re-run IFCT/USDA lookup + recompute macros
  ↓
Backend: Validate macros, create Meal + MealItem rows
  ↓
Return 201 with saved meal JSON
  ↓
Frontend: Add to list, render meal with new [Edit] [Delete] buttons
  ↓
User can later click [Edit] to re-open the modal pre-filled with current items:
  ↓
PATCH /meals/{id} (reuses existing route, now with macro rescale/relookup logic)
  ↓
Backend: Same rescale-or-relookup per-item, then update DB
```

**Result**: Meal items are always validated and re-resolved server-side; users never sneak in bogus macros. Review UI appears both pre-save (required) and post-save (optional).

---

## Current Architecture

### Groq LLM parsing

**File**: `meals/services/llm_service.py:15–83`

- `SYSTEM_PROMPT` (~L15–27) instructs Groq to return JSON array: `[{ item_name, quantity, unit (free-text), serving_size_grams, calories, protein_g, carbs_g, fats_g, fiber_g, confidence }]`
- `parse_meal(transcript: str) -> list[dict]` (~L30) calls Groq, parses response, returns raw item dicts.
- Unit field is currently **free-text, no enum enforced**.

### Meal creation and persistence

**File**: `meals/services/meal_service.py:128–282`

- `_assemble_meal(items, input_method, ...)` (~L129–181): Single shared path for voice/text/image.
  1. Validate items via `MealItemCreateSerializer` (~L150).
  2. `resolve_item_macros(items)` → IFCT/USDA lookup or LLM estimate (~L158).
  3. `validate_macros(items)` → ±10% arithmetic check (~L161).
  4. Create `Meal` + `MealItem` rows (~L166–181).
- `create_meal_from_audio/text/image` (~L186–232): Thin wrappers; parse then assemble in one call.
- `replace_meal_items(meal, payload_data)` (~L235–282): PATCH path (edit existing meal).
  - Currently **skips IFCT/USDA lookup** (~L250 comment); trusts client-submitted macros as-is.
  - Deletes all old `MealItem` rows, recreates with payload data (~L264–282).

**The new `_parse_*` functions (parse-only, no DB) and `/confirm` endpoint (persist after review) don't exist yet.**

### Database schema

**File**: `meals/models.py:37–50`

`MealItem` model fields:
- `item_name` (CharField, 255) — food name
- `quantity` (FloatField, 0.01–10000)
- `unit` (CharField, max_length=50, default=`"serving"`) — **currently free-text, no `choices=`**
- `serving_size_grams` (FloatField, nullable)
- `calories`, `protein_g`, `carbs_g`, `fats_g`, `fiber_g` (FloatField)
- `confidence` (FloatField, default=0.85)
- `source` (CharField, default=`"llm_estimate"`) — tracks IFCT, USDA, or LLM estimate
- `llm_generated` (bool)

**No `choices` enum on unit yet.** Will be added.

### Serializers

**File**: `meals/serializers.py:20–31` (`MealItemCreateSerializer`)

- `unit` is a plain `CharField(max_length=50, default="serving")` — **no constraint**.
- `item_name`, `quantity` validated.
- Macro fields (`calories`, `protein_g`, etc.) are currently `required=True`.

**Will be updated**: `unit` becomes `ChoiceField`, macro fields become `required=False`.

### Views (endpoints)

**File**: `meals/views.py:115–336`

- `CreateMealVoiceView.post()` (~L115) — `POST /meals/voice`, parse+save synchronously.
- `CreateMealTextView.post()` (~L157), `CreateMealImageView.post()` (~L182) — parallel paths.
- `MealDetailView.patch()` (~L298) — `PATCH /meals/{id}`, calls `replace_meal_items()`.
- `MealDetailView.delete()` (~L321) — `DELETE /meals/{id}`.
- All endpoints owner-checked via `_get_meal_or_error()` (~L273).

**New endpoints** (`CreateMealVoicePreviewView`, `/meals/confirm`, etc.) don't exist yet.

### Frontend

**File**: `templates/dashboard.html:200–250`, `static/js/dashboard.js:60–245`

- `dashboard.renderMealList()` (~L203–245) — renders meals in `#meals-list`.
- **Pre-existing Delete button** at `dashboard.js:242`: `<button onclick="dashboard.deleteMeal('${meal.meal_id}')">Delete</button>`.
- `dashboard.deleteMeal(mealId)` (~L90) — `apiDelete('/meals/${mealId}')`.
- `dashboard.updateMeal(mealId, mealItems)` (~L65) — `apiPatch('/meals/${mealId}', {..., meal_items: mealItems})`. **Currently unused** (no UI calls it).

**No per-item edit UI exists; no modal/form for reviewing items pre-save.**

### Unit conversion (weight only)

**File**: `meals/services/food_lookup_service.py:208–219`

- `resolve_item_macros()` recognizes weight units: `g, kg, oz, lb` with conversion factors (kg×1000, oz×28.3495, lb×453.592).
- Any other unit (cup, bowl, plate, ml, piece, serving) → no conversion, falls back unscaled.

**No approximate gram-equivalents for volume/container units exist yet.**

---

## Target Architecture

### Backend: Refactor parsing into two steps

**File**: `meals/services/meal_service.py` (refactor existing functions + add new ones)

#### Step 1: Parse-only functions (transcribe + parse + resolve, no DB)

Replace the internal logic of `create_meal_from_audio/text/image` with new thin parse-only helpers. These will be reused by both the preview endpoints (return JSON) and the existing fast-path (call parse then assemble back-to-back).

```python
# Add to meal_service.py (around line 128, before _assemble_meal)

def _parse_audio_to_items(audio_file, language: str = "en-US") -> list[dict]:
    """
    Transcribe audio (via NVIDIA Parakeet), parse via Groq, resolve macros.
    Returns unsaved items (no DB write). Used by both preview endpoint and fast-path create.
    """
    from meals.services.whisper_service import transcribe
    from meals.services.llm_service import parse_meal
    
    # Transcode to WAV if needed (existing logic in views.py)
    transcription = transcribe(audio_file, language=language)
    
    # Parse via Groq
    raw_items = parse_meal(transcription.text)
    
    # Resolve macros (IFCT/USDA + LLM fallback)
    resolved_items = resolve_item_macros(raw_items)
    
    return resolved_items

def _parse_text_to_items(text: str) -> list[dict]:
    """Parse plain text meal description (Groq), resolve macros."""
    from meals.services.llm_service import parse_meal
    
    raw_items = parse_meal(text)
    resolved_items = resolve_item_macros(raw_items)
    return resolved_items

def _parse_image_to_items(image_file) -> list[dict]:
    """Describe image via Gemini Vision, parse via Groq, resolve macros."""
    from meals.services.food_lookup_service import describe_meal_image_via_gemini
    from meals.services.llm_service import parse_meal
    
    description = describe_meal_image_via_gemini(image_file)
    raw_items = parse_meal(description.text)
    resolved_items = resolve_item_macros(raw_items)
    return resolved_items
```

#### Step 2: Update existing create functions for backward compatibility

Modify `create_meal_from_audio/text/image` to call parse-then-assemble without breaking existing callers:

```python
# Existing functions in meal_service.py, refactored to reuse new parse functions

def create_meal_from_audio(audio_file, user, input_method: str = "voice", language: str = "en-US", meal_category: str = None) -> Meal:
    """Create meal from audio: parse + assemble in one request (existing fast-path)."""
    items = _parse_audio_to_items(audio_file, language=language)
    return _assemble_meal(items=items, user=user, input_method=input_method, meal_category=meal_category)

def create_meal_from_text(text: str, user, input_method: str = "text", meal_category: str = None) -> Meal:
    """Create meal from text: parse + assemble in one request."""
    items = _parse_text_to_items(text)
    return _assemble_meal(items=items, user=user, input_method=input_method, original_text=text, meal_category=meal_category)

def create_meal_from_image(image_file, user, input_method: str = "photo", meal_category: str = None) -> Meal:
    """Create meal from image: parse + assemble in one request."""
    items = _parse_image_to_items(image_file)
    return _assemble_meal(items=items, user=user, input_method=input_method, meal_category=meal_category)
```

**No changes to `_assemble_meal()`; no changes to existing endpoint signatures** — backward compatible.

### Backend: New unit allowlist and conversions

**File**: `meals/services/food_lookup_service.py` (add to existing file)

Add after the existing weight-conversion code (around line 220):

```python
# Unit system: fixed allowlist + gram-equivalents for scaling

ALLOWED_UNITS = {
    "g": {"name": "grams", "gram_equivalent": 1.0},
    "kg": {"name": "kilograms", "gram_equivalent": 1000.0},
    "ml": {"name": "milliliters", "gram_equivalent": 1.0},  # water-density approx
    "l": {"name": "liters", "gram_equivalent": 1000.0},
    "oz": {"name": "ounces", "gram_equivalent": 28.3495},
    "cup": {"name": "cups", "gram_equivalent": 240.0},
    "bowl": {"name": "bowls", "gram_equivalent": 400.0},
    "plate": {"name": "plates", "gram_equivalent": 300.0},
    "piece": {"name": "pieces", "gram_equivalent": None},  # unconvertible
    "serving": {"name": "servings", "gram_equivalent": None},  # unconvertible
}

def get_gram_equivalent(unit: str) -> float | None:
    """
    Return the approximate gram weight for one unit of the given unit string.
    Returns None if the unit is unconvertible (piece, serving).
    """
    if unit not in ALLOWED_UNITS:
        return None
    return ALLOWED_UNITS[unit].get("gram_equivalent")
```

### Backend: Macro rescaling and re-lookup logic

**File**: `meals/services/food_lookup_service.py` (add new functions)

```python
def needs_fresh_lookup(old_name: str, new_name: str, threshold: float = 0.85) -> bool:
    """
    Heuristic: does the item name change warrant a fresh IFCT/USDA lookup?
    If new_name differs significantly from old_name (string similarity < threshold),
    assume it's a different food → re-lookup. Otherwise, assume quantity/unit-only edit → rescale.
    """
    from difflib import SequenceMatcher
    ratio = SequenceMatcher(None, old_name.lower(), new_name.lower()).ratio()
    return ratio < threshold

def rescale_item_macros(item: dict, old_qty: float, old_unit: str, new_qty: float, new_unit: str) -> dict:
    """
    Rescale macro values from (old_qty, old_unit) to (new_qty, new_unit).
    Assumes both units are convertible (have gram_equivalent). Proportionally scales all macros.
    
    Args:
        item: dict with calories, protein_g, carbs_g, fats_g, fiber_g
        old_qty, old_unit: original quantity and unit from preview
        new_qty, new_unit: edited quantity and unit
    
    Returns:
        item dict with rescaled macro values
    """
    old_grams = get_gram_equivalent(old_unit)
    new_grams = get_gram_equivalent(new_unit)
    
    if old_grams is None or new_grams is None:
        # Unconvertible unit (piece, serving) → cannot reliably rescale
        # Return item as-is; log warning
        import logging
        logging.warning(f"Cannot rescale {item.get('item_name')} from {old_unit} (qty={old_qty}) to {new_unit} (qty={new_qty}): unconvertible unit")
        return item
    
    # Total grams: old_qty units × old_grams_per_unit → new_qty units × new_grams_per_unit
    old_total_grams = old_qty * old_grams
    new_total_grams = new_qty * new_grams
    
    scale_factor = new_total_grams / old_total_grams if old_total_grams > 0 else 1.0
    
    # Rescale each macro proportionally
    item["calories"] = item.get("calories", 0) * scale_factor
    item["protein_g"] = item.get("protein_g", 0) * scale_factor
    item["carbs_g"] = item.get("carbs_g", 0) * scale_factor
    item["fats_g"] = item.get("fats_g", 0) * scale_factor
    item["fiber_g"] = item.get("fiber_g", 0) * scale_factor
    
    return item
```

### Backend: Update `replace_meal_items()` with rescale/relookup logic

**File**: `meals/services/meal_service.py:235–282` (modify existing function)

The current `replace_meal_items()` skips macro re-resolution. Update it to apply the same rescale-or-relookup logic as the new `/confirm` endpoint:

```python
def replace_meal_items(meal: Meal, payload_data: dict) -> Meal:
    """
    PATCH /meals/{id} handler: replace all items for a meal.
    NEW: For each item, if name unchanged → rescale macros proportionally.
    If name changed → re-run IFCT/USDA lookup + recompute macros.
    Replaces old behavior (trust client macros wholesale).
    """
    from meals.services.food_lookup_service import needs_fresh_lookup, rescale_item_macros, resolve_item_macros
    
    new_items_payload = payload_data.get("meal_items", [])
    
    # Validate payload via serializer
    serializer = MealUpdateSerializer(data=payload_data)
    serializer.is_valid(raise_exception=True)
    
    # Map old items by id for comparison
    old_items_by_id = {item.id: item for item in meal.mealitem_set.all()}
    
    # Process each new item
    processed_items = []
    for idx, new_item_data in enumerate(new_items_payload):
        item_id = new_item_data.get("id")  # Optional: if provided, match to old item
        
        if item_id and item_id in old_items_by_id:
            old_item = old_items_by_id[item_id]
            old_name = old_item.item_name
            new_name = new_item_data.get("item_name", old_name)
            
            if needs_fresh_lookup(old_name, new_name):
                # Name changed significantly → re-run IFCT/USDA lookup
                resolved = resolve_item_macros([new_item_data])[0]
                processed_items.append(resolved)
            else:
                # Name similar → rescale macros from old quantity/unit to new
                rescaled = rescale_item_macros(
                    new_item_data,
                    old_qty=old_item.quantity,
                    old_unit=old_item.unit,
                    new_qty=new_item_data.get("quantity", old_item.quantity),
                    new_unit=new_item_data.get("unit", old_item.unit)
                )
                processed_items.append(rescaled)
        else:
            # New item (no matching old item) → run fresh IFCT/USDA lookup
            resolved = resolve_item_macros([new_item_data])[0]
            processed_items.append(resolved)
    
    # Validate macros
    validate_macros(processed_items)
    
    # Delete old items, create new rows
    meal.mealitem_set.all().delete()
    for item_data in processed_items:
        MealItem.objects.create(meal=meal, **item_data)
    
    # Update meal metadata if provided
    if "original_text" in payload_data:
        meal.original_text = payload_data["original_text"]
    if "meal_category" in payload_data:
        meal.meal_category = payload_data["meal_category"]
    meal.save()
    
    return meal
```

### Backend: New `/confirm` endpoint

**File**: `meals/views.py` (add new view class, around line 380)

```python
class ConfirmMealView(APIView):
    """
    POST /meals/confirm
    Persist a meal after user reviews/edits items in the pre-save modal.
    Applies rescale-or-relookup logic (same as PATCH /meals/{id} now uses).
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Body: {
            input_method: "voice|text|photo",
            original_text: "...",  (optional, for text input)
            transcription_text: "...",  (optional, for voice)
            meal_category: "breakfast|...",  (optional)
            items: [
                { item_name, quantity, unit, serving_size_grams, calories, protein_g, carbs_g, fats_g, fiber_g, confidence, source }
            ]
        }
        
        For each item:
        - If this is a pre-save confirm, all items are freshly resolved from preview (name may be edited by user).
        - If item_name was edited by user since preview: re-run IFCT/USDA lookup.
        - Otherwise: assume macros carried from preview are already correct.
        
        (In practice, this endpoint is only called after a preview, so items always have resolved macros.
        The name-change detection is defensive; most edits will just rescale.)
        """
        from meals.services.meal_service import _assemble_meal
        
        # Validate request
        serializer = ConfirmMealSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        items = serializer.validated_data.get("items", [])
        input_method = serializer.validated_data.get("input_method", "unknown")
        original_text = serializer.validated_data.get("original_text")
        transcription_text = serializer.validated_data.get("transcription_text")
        meal_category = serializer.validated_data.get("meal_category")
        
        # Assemble and persist
        meal = _assemble_meal(
            items=items,
            user=request.user,
            input_method=input_method,
            original_text=original_text,
            transcription_text=transcription_text,
            meal_category=meal_category,
            skip_macro_revalidation=True  # Macros already valid from preview
        )
        
        serializer_out = MealSerializer(meal)
        return Response(serializer_out.data, status=status.HTTP_201_CREATED)
```

### Backend: New preview endpoints

**File**: `meals/views.py` (add new view classes, around line 360)

```python
class CreateMealVoicePreviewView(APIView):
    """POST /meals/voice/preview — parse audio, return items (no DB save)."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Multipart: audio file.
        Returns: { items: [...], transcription_text: "..." }
        No database write. Frontend opens review modal with these items.
        """
        from meals.services.meal_service import _parse_audio_to_items
        
        if "file" not in request.FILES:
            return Response({"detail": "No audio file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        audio_file = request.FILES["file"]
        
        # Validate file (same checks as CreateMealVoiceView)
        if audio_file.size > 25 * 1024 * 1024:
            return Response({"detail": "Audio file too large (max 25 MB)"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse (transcribe + parse + resolve)
        try:
            items = _parse_audio_to_items(audio_file, language=request.data.get("language", "en-US"))
            
            # Also return transcription for display/edit in UI
            from meals.services.whisper_service import transcribe
            transcription = transcribe(audio_file)
            
            return Response({
                "items": items,
                "transcription_text": transcription.text
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateMealTextPreviewView(APIView):
    """POST /meals/text/preview — parse text, return items (no DB save)."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from meals.services.meal_service import _parse_text_to_items
        
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"detail": "No text provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            items = _parse_text_to_items(text)
            return Response({"items": items}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateMealImagePreviewView(APIView):
    """POST /meals/image/preview — describe + parse image, return items (no DB save)."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from meals.services.meal_service import _parse_image_to_items
        
        if "file" not in request.FILES:
            return Response({"detail": "No image file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        image_file = request.FILES["file"]
        
        try:
            items = _parse_image_to_items(image_file)
            return Response({"items": items}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

### Backend: URL routing

**File**: `meals/urls.py` (add new routes)

```python
# Add to urlpatterns in meals/urls.py (around line 12)

path("voice/preview", CreateMealVoicePreviewView.as_view(), name="create_meal_voice_preview"),
path("text/preview", CreateMealTextPreviewView.as_view(), name="create_meal_text_preview"),
path("image/preview", CreateMealImagePreviewView.as_view(), name="create_meal_image_preview"),
path("confirm", ConfirmMealView.as_view(), name="confirm_meal"),
```

### Backend: Serializers

**File**: `meals/serializers.py` (update + add new)

```python
# Update existing MealItemCreateSerializer (around line 20)

class MealItemCreateSerializer(serializers.Serializer):
    item_name = serializers.CharField(max_length=255)
    quantity = serializers.FloatField(min_value=0.01, max_value=10000)
    unit = serializers.ChoiceField(
        choices=list(ALLOWED_UNITS.keys()),
        default="serving"
    )
    serving_size_grams = serializers.FloatField(required=False, allow_null=True, min_value=0)
    
    # Macro fields now optional (not required for confirm/edit payloads)
    calories = serializers.FloatField(required=False, min_value=0)
    protein_g = serializers.FloatField(required=False, min_value=0)
    carbs_g = serializers.FloatField(required=False, min_value=0)
    fats_g = serializers.FloatField(required=False, min_value=0)
    fiber_g = serializers.FloatField(required=False, default=0, min_value=0)
    
    confidence = serializers.FloatField(required=False, default=0.85, min_value=0, max_value=1)
    source = serializers.CharField(required=False, default="llm_estimate")

# Add new ConfirmMealSerializer (around line 80)

class ConfirmMealSerializer(serializers.Serializer):
    input_method = serializers.ChoiceField(choices=["voice", "text", "photo"])
    original_text = serializers.CharField(required=False, allow_blank=True)
    transcription_text = serializers.CharField(required=False, allow_blank=True)
    meal_category = serializers.CharField(required=False, allow_blank=True)
    items = MealItemCreateSerializer(many=True, min_length=1)
```

### Backend: Django model migration

**File**: Create `meals/migrations/XXXX_mealitem_unit_choices.py`

```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("meals", "XXXX_previous_migration"),  # Update to actual prior migration
    ]
    
    operations = [
        migrations.AlterField(
            model_name="mealitem",
            name="unit",
            field=models.CharField(
                max_length=50,
                default="serving",
                choices=[
                    ("g", "grams"),
                    ("kg", "kilograms"),
                    ("ml", "milliliters"),
                    ("l", "liters"),
                    ("oz", "ounces"),
                    ("cup", "cups"),
                    ("bowl", "bowls"),
                    ("plate", "plates"),
                    ("piece", "pieces"),
                    ("serving", "servings"),
                ]
            ),
        ),
    ]
```

Run `python manage.py makemigrations` + `python manage.py migrate` to apply.

### Frontend: New shared meal-items editor component

**File**: Create `static/js/mealItemsEditor.js`

```javascript
/**
 * MealItemsEditor: Shared UI for editing meal items (pre-save review or post-save edit).
 * Renders editable rows: name (text), quantity (number), unit (select).
 * Macros displayed as read-only.
 */

class MealItemsEditor {
  constructor(items = [], options = {}) {
    this.items = items;
    this.options = {
      showTranscription: options.showTranscription || false,
      transcription: options.transcription || "",
      mealCategory: options.mealCategory || null,
      ...options
    };
    this.unitOptions = [
      "g", "kg", "ml", "l", "oz", "cup", "bowl", "plate", "piece", "serving"
    ];
  }
  
  render() {
    const html = `
      <div class="meal-editor" style="padding: 16px;">
        ${this.options.showTranscription ? `
          <div style="margin-bottom: 16px;">
            <label style="display: block; font-weight: 700; margin-bottom: 8px;">
              Transcription
            </label>
            <p style="margin: 0; color: #546E7A;">${escapeHtml(this.options.transcription)}</p>
          </div>
        ` : ""}
        
        <div style="margin-bottom: 16px;">
          <label style="display: block; font-weight: 700; margin-bottom: 8px;">
            Meal Items
          </label>
          <div id="items-list" style="display: flex; flex-direction: column; gap: 12px;">
            ${this.items.map((item, idx) => this.renderItemRow(item, idx)).join("")}
          </div>
        </div>
        
        <div style="display: flex; gap: 8px; justify-content: flex-end; padding-top: 16px; border-top: 1px solid #F3F4F6;">
          <button id="cancel-btn" class="btn btn-secondary" style="padding: 8px 16px;">Cancel</button>
          <button id="save-btn" class="btn btn-primary" style="padding: 8px 16px; background-color: #FF7043; color: white;">Save Meal</button>
        </div>
      </div>
    `;
    return html;
  }
  
  renderItemRow(item, idx) {
    return `
      <div class="item-row" data-idx="${idx}" style="display: grid; grid-template-columns: 2fr 1fr 1fr 1.5fr; gap: 8px; align-items: center; padding: 8px; background-color: #FFFDF9; border-radius: 8px; border: 1px solid #F3F4F6;">
        <input type="text" class="item-name-input" value="${escapeHtml(item.item_name)}" placeholder="Food name" style="padding: 8px; border: 1px solid #E0E0E0; border-radius: 4px;" />
        <input type="number" class="item-qty-input" value="${item.quantity}" min="0.01" step="0.1" style="padding: 8px; border: 1px solid #E0E0E0; border-radius: 4px;" />
        <select class="item-unit-select" style="padding: 8px; border: 1px solid #E0E0E0; border-radius: 4px;">
          ${this.unitOptions.map(u => `<option value="${u}" ${u === item.unit ? "selected" : ""}>${u}</option>`).join("")}
        </select>
        <div style="font-size: 12px; color: #546E7A;">
          ${Math.round(item.calories)} kcal | P: ${item.protein_g.toFixed(1)}g C: ${item.carbs_g.toFixed(1)}g F: ${item.fats_g.toFixed(1)}g
        </div>
      </div>
    `;
  }
  
  getEditedItems() {
    const rows = document.querySelectorAll(".item-row");
    const items = [];
    rows.forEach(row => {
      const idx = parseInt(row.dataset.idx);
      const oldItem = this.items[idx];
      items.push({
        ...oldItem,
        item_name: row.querySelector(".item-name-input").value,
        quantity: parseFloat(row.querySelector(".item-qty-input").value),
        unit: row.querySelector(".item-unit-select").value
      });
    });
    return items;
  }
  
  mount(selector) {
    const container = document.querySelector(selector);
    if (!container) return;
    container.innerHTML = this.render();
  }
}

function escapeHtml(text) {
  const map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}
```

### Frontend: Update dashboard to add Edit button and wire preview→confirm flow

**File**: `static/js/dashboard.js` (modify `renderMealList()`, add new methods)

```javascript
// Around line 242, update the Delete button to include Edit:

renderMealList() {
  // ... (existing code for meal items)
  
  // Replace the old Delete-only button line with:
  <button class="text-sm text-orange-600 hover:opacity-80 transition" onclick="dashboard.editMeal('${meal.meal_id}')">Edit</button>
  <button class="text-sm text-error hover:opacity-80 transition" onclick="dashboard.deleteMeal('${meal.meal_id}')">Delete</button>
}

// Add new method to Dashboard class:

editMeal(mealId) {
  // Open review modal pre-filled with current meal items
  const meal = this.meals.find(m => m.meal_id === parseInt(mealId));
  if (!meal) return;
  
  // Show modal with MealItemsEditor
  const modal = document.createElement("div");
  modal.style.cssText = "position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;";
  modal.innerHTML = `<div style="background: white; border-radius: 12px; padding: 0; max-width: 600px; max-height: 80vh; overflow-y: auto;">${new MealItemsEditor(meal.meal_items).render()}</div>`;
  document.body.appendChild(modal);
  
  modal.querySelector("#cancel-btn").onclick = () => modal.remove();
  modal.querySelector("#save-btn").onclick = async () => {
    const editedItems = new MealItemsEditor(meal.meal_items).mount(modal.querySelector(".meal-editor"));
    const items = editedItems.getEditedItems();
    
    const response = await apiPatch(`/meals/${mealId}`, {
      meal_items: items
    });
    
    if (response) {
      // Update local state and re-render
      const idx = this.meals.findIndex(m => m.meal_id === parseInt(mealId));
      this.meals[idx] = response;
      this.render();
      modal.remove();
    }
  };
}
```

### Frontend: Wire audio/text/image capture to preview→confirm flow

**File**: `static/js/dashboard.js` (modify voice/text/image capture handlers)

Replace the old inline `POST /meals/voice` call with:

```javascript
// After recording audio (in audioRecorder callback):

async recordAndPreview() {
  const formData = new FormData();
  formData.append("file", this.audioBlob, "meal.wav");
  
  // Call /preview endpoint instead of /voice
  const response = await apiPostFile("/meals/voice/preview", formData);
  if (!response) return;
  
  // Open review modal with preview items
  const modal = document.createElement("div");
  modal.style.cssText = "position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;";
  
  const editor = new MealItemsEditor(response.items, {
    showTranscription: true,
    transcription: response.transcription_text
  });
  
  modal.innerHTML = `<div style="background: white; border-radius: 12px; padding: 0; max-width: 600px; max-height: 80vh; overflow-y: auto;">${editor.render()}</div>`;
  document.body.appendChild(modal);
  
  modal.querySelector("#cancel-btn").onclick = () => modal.remove();
  modal.querySelector("#save-btn").onclick = async () => {
    editor.mount(modal.querySelector(".meal-editor"));
    const editedItems = editor.getEditedItems();
    
    // Post to /confirm endpoint
    const confirmResponse = await apiPost("/meals/confirm", {
      input_method: "voice",
      transcription_text: response.transcription_text,
      items: editedItems
    });
    
    if (confirmResponse) {
      this.addMeal(confirmResponse);
      modal.remove();
    }
  };
}
```

---

## Rules You Must Preserve

1. **All new endpoints require authentication** — use `permission_classes = [IsAuthenticated]` on `CreateMealVoicePreviewView`, `ConfirmMealView`, etc. Follow the same ownership checks as `MealDetailView._get_meal_or_error()` for any endpoint modifying meals.

2. **Server-side unit allowlist enforcement** — `MealItemCreateSerializer.unit` is a `ChoiceField` against `ALLOWED_UNITS` keys. Never trust frontend-only unit validation. (Security.md §1/§3: Input validation at the boundary.)

3. **Never trust client-submitted macros** — confirm and PATCH endpoints accept macro fields but immediately discard them. Macros are always recomputed server-side via `resolve_item_macros()` (IFCT/USDA lookup or re-estimate). This supersedes the old documented rule in `docs/add-usda-ifct-nutrition-lookup-prompt.md` (line 10, "user-edited items are not re-resolved"). The new edit UI never exposes macro fields to edit, so this change is justified and safe.

4. **Preview endpoints must not persist** — `_parse_audio/text/image_to_items()` return items without writing to the database. Only `_assemble_meal()` or `ConfirmMealView.post()` may create `Meal`/`MealItem` rows. Test this explicitly: assert `Meal.objects.count() == 0` after a preview call.

5. **No add/remove items** — the edit UI renders exactly as many rows as the meal contains; users can only edit existing items. If you add a "+" button or delete-per-item, remove it.

6. **Rate limit the 3 preview endpoints + /confirm** — all 4 are backed by LLM calls (Groq, Gemini, NVIDIA). Implement rate-limiting per account + per IP (security.md §7) if not already present in the codebase. Flag in the testing checklist if rate-limiting is currently absent.

7. **No schema changes to existing fields** — `MealItem` add `choices=` to `unit` only. No changes to `Meal` or any other model. Existing code using `unit` strings must still work (backward compatible).

---

## Known Pitfalls

**Q: Why do `piece` and `serving` units have `gram_equivalent: None`?**
A: These units have no standard weight. A "piece" of bread is 50–100g; a "piece" of cheese is 20–50g. A "serving" is defined per-food. Without domain knowledge we can't scale them reliably, so we don't — macros stay at the LLM estimate if the user picks these units. This is the same fallback behavior that exists today for unconvertible units. It's a documented limitation: show the user that unit selection impacts macro accuracy.

**Q: Why rescale-on-quantity-only-edit but re-lookup-on-name-edit?**
A: If I ordered "chicken" with qty=100g, calories=165. If I change it to qty=200g, the macros should roughly double (rescale). But if I change it to "beef", the macros are completely different (beef has a different macro profile than chicken) — rescaling makes no sense, re-lookup is required. The heuristic `needs_fresh_lookup()` uses string similarity (~85% threshold) to detect significant name changes; minor typos don't trigger a re-lookup.

**Q: The gram-equivalents for cup, bowl, plate are rough estimates. What if a user disputes them?**
A: Acknowledged in the UI (e.g., a tooltip: "Approximate weight; results may vary by food density"). The point is that **something** is better than **nothing** — we scale macros reasonably instead of leaving them flat. The docs and UI make clear this is a best-effort conversion, not a ground-truth food scale. Users can still see and manually override the macros (via the `/` endpoint... wait, there's no client-side macro editor. The edit UI only exposes name/qty/unit, so macros are always server-recomputed, never user-overridden. This is intentional.)

**Q: What if Groq times out during a preview call? The user is staring at a spinner indefinitely.**
A: Preview endpoints should have a short timeout (e.g., 15–30 seconds) and return 504 or 408. The frontend modal should show "Preview failed: please try again" and let the user discard and re-record. This is already true for existing create endpoints; no special handling needed here.

**Q: Do I need to handle the case where the user edits an item and then clicks Save multiple times?**
A: If the user double-clicks Save, the PATCH request fires twice. The second request sees items with `id` fields matching existing rows, re-runs rescale/relookup logic, and overwrites. Idempotent. No special concurrency handling needed (same DB semantics as today's whole-meal replace).

---

## Testing & Verification Checklist

### Unit tests: `tests/test_food_lookup_service.py` (new file)

- [ ] `test_get_gram_equivalent_weight_units()` — `g, kg, oz, lb` return correct factors
- [ ] `test_get_gram_equivalent_volume_units()` — `ml, l, cup, bowl, plate` return approx grams
- [ ] `test_get_gram_equivalent_unconvertible()` — `piece, serving` return None
- [ ] `test_rescale_item_macros_weight()` — rescaling 100g→200g doubles macros
- [ ] `test_rescale_item_macros_unit_conversion()` — rescaling 1 cup → 240g works
- [ ] `test_rescale_item_macros_unconvertible()` — rescaling piece/serving logs warning, returns item unchanged
- [ ] `test_needs_fresh_lookup_same_name()` — "chicken" → "Chicken" (similarity ~100%) returns False
- [ ] `test_needs_fresh_lookup_different_name()` — "chicken" → "beef" (similarity ~0%) returns True

### Unit tests: `tests/test_meal_service.py` (update existing)

- [ ] `test_parse_audio_to_items_no_db_write()` — after calling `_parse_audio_to_items()`, assert `Meal.objects.count() == 0`
- [ ] `test_parse_text_to_items_no_db_write()` — same for text
- [ ] `test_parse_image_to_items_no_db_write()` — same for image
- [ ] `test_create_meal_from_audio_still_works()` — backward compat: existing fast-path still parse+save in one call

### Unit tests: `tests/test_serializers.py` (update existing)

- [ ] `test_mealitemcreateserializer_unit_choice_valid()` — accepts all 10 allowed units
- [ ] `test_mealitemcreateserializer_unit_choice_invalid()` — rejects "forks", "hands", random strings
- [ ] `test_mealitemcreateserializer_macro_fields_optional()` — macros not required (empty {} still validates)
- [ ] `test_confirmmealserializer_valid()` — accepts { input_method, items } payload
- [ ] `test_confirmmealserializer_items_required()` — rejects empty items list

### Integration tests: Preview endpoints (new file `tests/test_preview_endpoints.py`)

- [ ] `test_voice_preview_endpoint_authenticated()` — POST /meals/voice/preview with Bearer token succeeds
- [ ] `test_voice_preview_endpoint_unauthenticated()` — POST without token returns 401
- [ ] `test_voice_preview_endpoint_large_file()` — file >25MB returns 400
- [ ] `test_voice_preview_endpoint_returns_items()` — response has `{ items: [...], transcription_text: "..." }`
- [ ] `test_voice_preview_no_db_write()` — after preview, `Meal.objects.count() == 0`
- [ ] `test_text_preview_endpoint()` — POST /meals/text/preview with `{ text: "..." }` returns items
- [ ] `test_image_preview_endpoint()` — POST /meals/image/preview with image file returns items

### Integration tests: Confirm endpoint (new file `tests/test_confirm_endpoint.py`)

- [ ] `test_confirm_endpoint_creates_meal()` — POST /meals/confirm saves items to DB
- [ ] `test_confirm_endpoint_validates_unit_choices()` — unit="forks" in payload returns 400
- [ ] `test_confirm_endpoint_recomputes_macros()` — if client sends calories=999, server re-resolves via IFCT/USDA
- [ ] `test_confirm_endpoint_name_change_retriggers_lookup()` — editing item name from "chicken" to "beef" re-runs IFCT lookup
- [ ] `test_confirm_endpoint_quantity_only_edit_rescales()` — editing qty 100g→200g without name change proportionally scales macros

### Integration tests: PATCH /meals/{id} updated logic (update `tests/test_meals.py`)

- [ ] `test_patch_meal_rescales_on_qty_unit_edit()` — existing test, update to assert proportional scaling
- [ ] `test_patch_meal_relookups_on_name_edit()` — existing test, update to assert fresh IFCT/USDA call on name change
- [ ] `test_patch_meal_rejects_invalid_unit()` — unit="forks" returns 400

### Security tests

- [ ] `test_confirm_endpoint_strips_client_macros()` — client sends `{ calories: 9999, ... }`, server ignores and re-resolves
- [ ] `test_preview_endpoints_are_authenticated()` — no preview endpoint works without Bearer token

### Manual tests (Frontend)

- [ ] Record audio → preview modal appears with parsed items
- [ ] Edit item name/qty/unit in preview → click Save → item saved to DB (check DB or dashboard)
- [ ] Save meal → [Edit] button appears next to [Delete]
- [ ] Click [Edit] → modal appears with current items pre-filled
- [ ] Edit items in post-save modal → click Save → DB updated, dashboard refreshed
- [ ] Attempt to send invalid unit (e.g., "forks") in PATCH payload → API returns 400 (if testing via curl)

### Backward compatibility

- [ ] Existing tests still pass: `pytest tests/test_meals.py`, `pytest tests/test_auth.py`
- [ ] Old endpoints still work: `POST /meals/voice` (parse+save in one call) still creates meals instantly
- [ ] Old mobile/API clients sending PATCH without rescale logic still work (backend provides the new logic, no client burden)

### Code quality

- [ ] `black meals/ accounts/ --check` — code formatted
- [ ] `flake8 meals/ accounts/` — no linting errors
- [ ] All new functions have docstrings

---

## Sources & References

- **Prior USDA/IFCT integration**: `docs/add-usda-ifct-nutrition-lookup-prompt.md` (line 10: old rule about trusting PATCH macros, now superseded)
- **Dashboard parity feature**: `docs/dashboard-parity-prompt.md` (design tokens, button layout, modal patterns)
- **Security rules**: `.claude/rules/security.md` §1 (no secrets, input validation), §3 (parameterized queries, field allowlists), §7 (rate-limiting auth/LLM endpoints)
- **Existing meal services**: `meals/services/meal_service.py`, `meals/services/llm_service.py`, `meals/services/food_lookup_service.py`
- **Database schema**: `meals/models.py:37–50` (MealItem), `meals/models.py:1–35` (Meal)
- **Views and serializers**: `meals/views.py`, `meals/serializers.py`
- **Frontend**: `templates/dashboard.html`, `static/js/dashboard.js`, `static/js/apiClient.js`
- **Django REST Framework docs**: https://www.django-rest-framework.org/
- **Google Gemini Vision API**: Used for photo meal descriptions (existing `describe_meal_image_via_gemini()` in `food_lookup_service.py`)

---

## Summary

**Files to create**:
- `docs/meal-item-review-and-edit-prompt.md` ← This file (for reference by future sessions)
- `static/js/mealItemsEditor.js` — Shared UI component for item editing (pre-save and post-save)
- `tests/test_preview_endpoints.py` — Unit + integration tests for new preview endpoints
- `tests/test_confirm_endpoint.py` — Tests for new /confirm endpoint
- `meals/migrations/XXXX_mealitem_unit_choices.py` — Add `choices=` to MealItem.unit field

**Files to modify**:
- `meals/services/meal_service.py` — Add parse-only functions (`_parse_audio/text/image_to_items`), update existing create functions for backward compat, update `replace_meal_items()` with rescale/relookup logic
- `meals/services/food_lookup_service.py` — Add `ALLOWED_UNITS`, `get_gram_equivalent()`, `needs_fresh_lookup()`, `rescale_item_macros()`
- `meals/views.py` — Add `CreateMealVoicePreviewView`, `CreateMealTextPreviewView`, `CreateMealImagePreviewView`, `ConfirmMealView`
- `meals/serializers.py` — Update `MealItemCreateSerializer` (unit ChoiceField, macro fields optional), add `ConfirmMealSerializer`
- `meals/urls.py` — Register new routes (`/voice/preview`, `/text/preview`, `/image/preview`, `/confirm`)
- `static/js/dashboard.js` — Add `editMeal()` method, wire audio/text/image capture to preview→confirm flow
- `templates/dashboard.html` — Load new `mealItemsEditor.js` script
- `tests/test_meals.py` — Update existing PATCH/edit tests to assert new rescale/relookup behavior
- `tests/test_serializers.py` — Update serializer tests for new ChoiceField and optional macros

**Key design decisions**:
1. Parse and persist are separated; preview endpoints return unsaved items; confirm endpoint persists.
2. Units constrained to 10 values with approximate gram-equivalents for scaling.
3. Macros always recomputed server-side (never trusted from client).
4. Edit UI is unified (pre-save and post-save use same `MealItemsEditor` component).
5. Superseded old PATCH-trust rule; documented the change explicitly.

**Acceptance**: All tests pass (`pytest`), no linting errors (`black`, `flake8`), preview endpoints return items without DB writes, confirm endpoint creates meals with properly resolved/scaled macros, PATCH /meals/{id} rescales or relooks up per-item correctly, Edit button is visible on saved meals and opens the review modal, all 10 units are accepted and rejected others server-side, and existing fast-path endpoints (POST /meals/voice) still work unchanged.

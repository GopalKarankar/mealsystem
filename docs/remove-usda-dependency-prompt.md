# Remove USDA FDC Nutrition Lookup Dependency — Dev Prompt

**Purpose**: This document explains why and how the USDA FoodData Central nutrition-lookup dependency was removed from this meal-tracking system. It serves as a reference for future sessions extending nutrition logic, so they understand the current (LLM-only) architecture and don't accidentally reintroduce the old lookup pattern or assume a seeded `foods` collection exists.

---

## Context: Before and After

### Before (USDA Dependency)

The original architecture performed nutrition lookup via a seeded MongoDB `foods` collection:

```
LLM parse meal
  ↓ (LLM estimates macros for each item)
Groq Llama → MealItem { item_name, calories, protein_g, ... }
  ↓
[NEW] food_lookup_service.resolve_item_macros()
  ↓ (two-tier lookup: exact → text search)
foods collection (USDA FDC SR Legacy bulk CSV seed)
  ↓
  IF match found:
    override macros with USDA data,
    floor confidence at 0.90,
    set source="usda_fdc"
  ELSE:
    keep LLM macros,
    discount confidence ×0.7,
    set source="llm_estimate"
  ↓
nutrition_service.validate_macros()
  ↓ (±10% calorie sanity check)
Save meal to DB
```

**Why it existed**: USDA data is more authoritative than LLM estimates, especially for common foods. A banana's nutrition is well-known and unlikely to vary; using that instead of an LLM guess improves accuracy.

**Cost**: Multi-GB CSV download, seed script (`scripts/seed_foods.py`), MongoDB food collection + indexes, `food_lookup_service` module, test fixtures.

### After (LLM Only)

The lookup step was removed entirely:

```
LLM parse meal
  ↓ (LLM estimates macros for each item)
Groq Llama → MealItem { item_name, calories, protein_g, ..., source=None }
  ↓
[REMOVED] food_lookup_service.resolve_item_macros()
  ↓
nutrition_service.validate_macros()
  ↓ (±10% calorie sanity check, fixes source to "llm_estimate" if still None)
Save meal to DB with source="llm_estimate"
```

**Trade-off**: Simpler architecture, no external data dependency, but all macro estimates come from Groq Llama's own LLM. Quality depends on prompt quality and Groq's training data.

---

## Files Removed

```
backend/app/services/food_lookup_service.py     # find_food_match(), resolve_item_macros()
backend/scripts/seed_foods.py                   # USDA CSV → foods collection seeding
backend/scripts/__init__.py                     # (scripts/ directory deleted)
backend/tests/test_food_lookup_service.py       # tests for food lookup service
backend/tests/test_seed_foods.py                # tests for seed script
backend/data/usda_fdc/                          # USDA CSV files (food.csv, etc.)
```

---

## Files Changed

### `backend/app/services/meal_service.py`

**Before**:
```python
from app.services import whisper_service, llm_service, nutrition_service, embedding_service, food_lookup_service

def create_meal_from_audio(user_id, audio_path: str, db) -> dict:
    ...
    looked_up_items = [
        food_lookup_service.resolve_item_macros(v.model_dump(), db) for v in validated
    ]
    ...
    "source": item_data.get("source", "llm_estimate"),  # BUG: stored None if source is None
```

**After**:
```python
from app.services import whisper_service, llm_service, nutrition_service, embedding_service

def create_meal_from_audio(user_id, audio_path: str, db) -> dict:
    ...
    looked_up_items = [v.model_dump() for v in validated]
    ...
    "source": item_data.get("source") or "llm_estimate",  # FIX: ensure source is never None
```

**Also in `replace_meal_items()`**: No change to how `source` is set (still hardcoded to `"Claude"`, a separate pre-existing inconsistency).

### `backend/app/config.py`

**Before**:
```python
class Settings(BaseSettings):
    ...
    food_seed_data_dir: str = "data/usda_fdc"
```

**After**:
```python
class Settings(BaseSettings):
    # food_seed_data_dir removed (no longer used)
```

### `backend/tests/test_meal_service.py`

**Removed**:
- Import: `from app.services.food_lookup_service import normalize_food_name`
- Fixture: `seed_with_foods()` (used to populate test DB with USDA food data)

**Renamed/Rewritten**:
- `test_meal_with_matched_and_unmatched_items()` → `test_meal_items_use_llm_estimates_directly()`
  - Removed the dual-outcome pattern (matched vs. unmatched)
  - Now asserts both items use `source="llm_estimate"` and confidence = LLM value (not discounted/floored)
  - Removed `seed_with_foods` fixture parameter

**Updated**:
- `test_validate_macros_runs_post_lookup()` → `test_validate_macros_runs_after_llm_parse()`
  - Removed `seed_with_foods` fixture parameter; logic otherwise unchanged
- `test_qdrant_failure_doesnt_fail_meal_save()` — removed `seed_with_foods` fixture parameter
- `test_source_field_in_response()` — changed assertions from `"usda_fdc"` to `"llm_estimate"`

---

## Rules You Must Preserve Going Forward

1. **No secondary nutrition override**: Meal item macros and confidence come directly from the LLM parse (`llm_service.parse_meal()`). Do not add another lookup/override step without a compelling reason (and update this doc).

2. **Source field must always be set**: Every MealItem must have `source` set to a real value ("llm_estimate" or a new source type name). Never allow it to be `None` in the saved document.
   - If you add a new nutrition data source, update the defaulting logic in `create_meal_from_audio()` to set `source` to the new type.

3. **Confidence is not discounted for missing lookup**: With no lookup, there's no "item not found" scenario. Confidence stays as the LLM provided it, sanity-checked only by `validate_macros()` (arithmetic check, no adjustment).

4. **`nutrition_service.validate_macros()` is the only macro validation step**: After LLM parse, only this function can adjust reported calories (if they're >10% off from protein/carb/fat arithmetic). It does not override confidence.

---

## If You Need Nutrition Lookup Again

Do not simply revert these files from git history. Instead:

1. **Assess the benefit**: Is the added accuracy worth multi-GB data maintenance + seeding overhead + a non-real-time data source?
2. **Consider alternatives**:
   - **Free API**: Use an external nutrition API (e.g., USDA FDC API directly, Nutritionix, Edamam) instead of a seeded collection.
   - **Cached/lighter dataset**: Seed only a curated subset of common foods (not 300k+ entries), or fetch from an API on-demand with TTL caching.
   - **Hybrid**: Trust LLM for unfamiliar items but require user confirmation for common foods flagged as uncertain.

3. **If reverting to seeded lookup**:
   - Restore `backend/app/services/food_lookup_service.py` from git history (commit that removed it).
   - Restore `backend/scripts/seed_foods.py` and download USDA FDC data.
   - Update `meal_service.create_meal_from_audio()` to call `food_lookup_service.resolve_item_macros()` after Pydantic validation.
   - Restore `test_food_lookup_service.py` and `test_seed_foods.py`.
   - Update `CLAUDE.md` "Seed the foods collection" section and documentation.

---

## Verification Checklist

After this change, confirm:

- [ ] `pytest tests/test_meal_service.py -v` passes (4 tests, all green)
- [ ] `pytest` (full suite) passes, no import errors for `food_lookup_service`
- [ ] `grep -ri "food_lookup\|seed_foods\|usda\|fdc" backend/app backend/tests` returns no matches (except in this doc or git history)
- [ ] `backend/app/config.py` has no `food_seed_data_dir` setting
- [ ] `CLAUDE.md` "Backend Structure" section lists no `food_lookup_service.py` or `scripts/`
- [ ] Manual test: POST `/meals/voice` with audio, confirm response `meal_items[].source == "llm_estimate"` for all items

---

## Known Pitfalls

**Q: Why does my meal have low confidence after removing USDA lookup?**  
A: Confidence is now purely what Groq Llama outputs. If the transcript is vague ("I ate stuff"), the LLM will rate confidence low. This is expected. Improve by using clearer descriptions in the transcript, or adjust the Groq prompt in `llm_service.py`.

**Q: I see `source=None` in some saved meals from before this change. Should I fix them?**  
A: Not urgent, but you can run:
```python
db.meals.update_many(
    {"meal_items.source": None},
    [{"$set": {"meal_items": [{"$mergeObjects": [
        "$$this",
        {"source": "llm_estimate"}
    ]}]}}]
)
```
to backfill them. This is a data cleanup, not required for functionality.

**Q: Can I add USDA lookup back as optional (feature flag)?**  
A: Possible, but adds complexity. Better to decide: either remove it entirely (current state) or keep it always-on. The in-between state (optional flag, dual code paths) obscures the architecture.

---

## Context for Future Sessions

- The decision to remove USDA dependency was made on 2026-09-07 to simplify the system and reduce external data maintenance.
- Groq Llama 3.3-70b provides reasonable macro estimates for typical foods; accuracy is acceptable for a tracking app where users can always edit.
- If accuracy becomes a user pain point, revisit this decision and implement a lightweight API-based lookup instead of a seeded collection.

---

## Note: USDA/IFCT Lookup Reintroduced (2026-09-11)

As of 2026-09-11, a new implementation (`docs/add-usda-ifct-nutrition-lookup-prompt.md`) reintroduces nutrition lookup using the exact approach recommended in "If You Need Nutrition Lookup Again" (§ this document, lines 151–166):

- **USDA FDC via live API** (no bulk CSV download, no seeding, minimal overhead)
- **IFCT as a small curated bundled dataset** (~100–500 common Indian foods, not the multi-GB seeding anti-pattern)
- **On-demand lookup** with graceful fallback to LLM if any API/match fails
- Uses the existing `MealItem.source` field ("ifct", "usda_fdc", or "llm_estimate")

This avoids the pitfalls that prompted this document's removal (maintenance burden, data staleness, seeding complexity) while recovering the accuracy benefit of authoritative nutrition data. Refer to `docs/add-usda-ifct-nutrition-lookup-prompt.md` for implementation details.


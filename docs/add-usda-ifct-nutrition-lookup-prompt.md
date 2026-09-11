# Add USDA FDC + IFCT Nutrition Lookup — Dev Prompt

**Purpose**: This prompt instructs you to integrate USDA FoodData Central (via live API) and IFCT (Indian Food Composition Tables, via bundled curated dataset) as authoritative nutrition data sources for meal items. When a food is recognized in either database, its calorie/macro values override the LLM estimate, improving accuracy especially for common and Indian foods. This is a practical on-demand alternative to the bulk-CSV approach that was deliberately removed in 2026-09-07; see `docs/remove-usda-dependency-prompt.md` for that prior design and its removal rationale.

**Scope decisions**:
- IFCT is sourced as a **bundled JSON file** (no live API exists), with a curated subset of common Indian foods (~100–500 entries) from published IFCT 2017 data. The implementing session will expand this set responsibly — do not fabricate nutrition numbers.
- USDA lookup calls the **FDC API live** (`api.nal.usda.gov`) with simple HTTP requests (no bulk data download or seeding).
- **Priority**: IFCT first → USDA FDC fallback → LLM estimate (if neither matches).
- Matched items set `source="ifct"` or `"usda_fdc"` in the database; unmatched items keep `source="llm_estimate"` (existing behavior).
- The lookup step is **wired only into LLM-parsed meal creation** (`create_meal_from_audio/text/image`); **user-edited items in PATCH requests are not re-resolved** to avoid silently changing user-authored numbers.
- Security: parameterized USDA API calls, no secret logging, timeout/error resilience (failures do not block meal save).

---

## Context: Before and After

### Before (LLM Estimates Only)

Today, all macro data comes from Groq Llama 3.3-70B estimation:

```
User records meal (voice/text/photo)
  ↓
Transcribe / Describe via LLM
  ↓
Parse meal via Groq Llama:
  "estimate [food] nutrition using standard nutrition knowledge"
  ↓ (LLM returns item_name, calories, protein_g, carbs_g, fats_g, fiber_g, confidence)
Validate macros (±10% arithmetic check)
  ↓
Save Meal + MealItem with source="llm_estimate"
```

This is simpler (no external DB dependency, no rate limits, no data maintenance) but relies entirely on Groq's training data and prompt quality. Accuracy is acceptable for a self-tracked app (users can edit), but common/authoritative foods are subject to LLM drift.

### After (LLM + Lookup Override)

Matched items now use authoritative nutrition data:

```
User records meal (voice/text/photo)
  ↓
Transcribe / Describe via LLM
  ↓
Parse meal via Groq Llama
  ↓
[NEW] Try to match each food in IFCT → USDA FDC:
  IF match found in IFCT:
    scale IFCT per-100g data by serving size
    override calories/macros
    set source="ifct"
  ELSE IF match found in USDA:
    scale USDA per-100g data by serving size
    override calories/macros
    set source="usda_fdc"
  ELSE:
    keep LLM estimate
    set source="llm_estimate"
  ↓
Validate macros (±10% check, now catches bad curated entries)
  ↓
Save Meal + MealItem with source tracking
```

Confidence is raised to ≥0.90 on match (matched foods are more authoritative). Unmatched items fall back to LLM as before.

---

## Current Architecture

### Meal item assembly (all three input paths converge here)

**File**: `meals/services/meal_service.py:128–181` (`_assemble_meal`)

Flow (shared by `create_meal_from_audio`, `create_meal_from_text`, `create_meal_from_image`):
1. Validate raw LLM-parsed items via `MealItemCreateSerializer` (strips unparseable items).
2. `validate_macros(validated)` — pure arithmetic: expected_calories = (protein_g×4) + (carbs_g×4) + (fats_g×9). If off by >10%, correct to nearest 5 kcal; logs warnings.
3. Compute mean `confidence_score` from items.
4. Create `Meal` + `MealItem` rows, setting `source=item_data.get("source") or "llm_estimate"`.

**The lookup step does not exist yet.** It will be inserted between validation (step 1) and macro sanity-check (step 2).

### Database schema

**File**: `meals/models.py`

`MealItem` fields of interest:
- `item_name` (CharField, 255) — what the user/LLM called the food
- `serving_size_grams` (FloatField, nullable) — grams of the serving (used to scale per-100g reference data)
- `quantity`, `unit` — user/LLM-provided amount (e.g., "2 cups")
- `calories`, `protein_g`, `carbs_g`, `fats_g`, `fiber_g` (FloatField) — the macro values
- `confidence` (FloatField, 0–1) — how sure we are (LLM estimate)
- `source` (CharField, default `"llm_estimate"`) — **already exists**, will be used to track "ifct", "usda_fdc", or "llm_estimate"

**No schema migration needed** — the `source` field already exists; this task just populates it differently.

### Serialization

**File**: `meals/serializers.py:20–31` (`MealItemCreateSerializer`)

Already accepts `source` as an optional CharField. No changes needed.

### Nutrition validation

**File**: `meals/services/nutrition_service.py:7–46` (`validate_macros`)

Pure arithmetic validation. Will be preserved as-is; now also acts as a safety net for bad curated-dataset entries.

### Groq LLM prompt

**File**: `meals/services/llm_service.py:15–27` (SYSTEM_PROMPT)

Instructs Groq to "estimate nutrition using standard nutrition knowledge." The prompt does not mention any database lookup, and will not be changed. Lookup happens *after* LLM parse.

---

## Target Architecture

### New service module: `meals/services/food_lookup_service.py`

Create this file with three functions:

#### `lookup_ifct(item_name: str) -> dict | None`

Normalized-name lookup against the bundled IFCT dataset.

```python
def lookup_ifct(item_name: str) -> dict | None:
    """
    Look up a food item in IFCT (bundled curated dataset).
    Returns per-100g nutrition data + metadata, or None if not found.
    
    Args:
        item_name: e.g., "rice", "daal", "roti"
    
    Returns:
        {
            "item_name": "...",
            "calories_per_100g": 130.0,
            "protein_g_per_100g": 2.7,
            "carbs_g_per_100g": 28.0,
            "fats_g_per_100g": 0.3,
            "fiber_g_per_100g": 0.4,
            "aliases": ["basmati", "white rice"],  # alternative names matched
            "source": "ifct",
            "source_detail": "IFCT 2017, NIN (Longvah et al.)"
        }
        or None
    """
```

Implementation: normalize `item_name` (lowercase, strip whitespace, remove punctuation), then try exact match in the bundled `meals/data/ifct_foods.json`. If no exact match, check each entry's `aliases` list for a normalized-name hit. Return the first match or None. Never raise exceptions; log misses at debug level.

#### `lookup_usda(item_name: str) -> dict | None`

Live API call to USDA FDC.

```python
def lookup_usda(item_name: str) -> dict | None:
    """
    Look up a food item in USDA FoodData Central.
    Returns per-100g nutrition data for the first result, or None if API fails/no match.
    
    Args:
        item_name: e.g., "banana", "chicken breast"
    
    Returns:
        {
            "item_name": "...",
            "calories_per_100g": 89.0,
            "protein_g_per_100g": 1.09,
            "carbs_g_per_100g": 23.0,
            "fats_g_per_100g": 0.33,
            "fiber_g_per_100g": 2.6,
            "fdc_id": "168101",
            "source": "usda_fdc",
            "source_detail": "FDC v1, Foundation/SR Legacy"
        }
        or None
    """
```

Implementation:
1. Build request: `GET {settings.USDA_API_BASE_URL}/foods/search` with `params={"query": item_name, "api_key": settings.USDA_API_KEY, "pageSize": 1, "dataType": ["Foundation", "SR Legacy"]}`
2. **Use parameterized query** (`params=` dict); never string-interpolate the URL. This avoids injection (security.md §3).
3. Timeout: 5 seconds; maximum retry: 1 (no aggressive retries, since meals should not hang on API hiccup).
4. On any error (timeout, non-200, JSON parse failure, missing fields), log a warning with the item name and return None. **Never raise an exception.**
5. Extract `foodNutrients` array from the first result; map USDA nutrient IDs to macros (1003=protein, 1005=carbs, 1004=fats, 1079=fiber, 1008=energy in kcal). Scale energy from kcal/100g.
6. Return the extracted dict or None.

**Caching recommendation** (optional, not required): Use Django's `@cache.cache_page()` or `functools.lru_cache` with a 24-hour TTL on successful USDA hits. The API allows ~1000 calls/hr with a real key; DEMO_KEY is ~30/hr. Caching avoids re-querying common foods (rice, banana, etc.) across multiple meals.

#### `resolve_item_macros(item: dict) -> dict`

Orchestrator: IFCT → USDA → LLM fallback.

```python
def resolve_item_macros(item: dict) -> dict:
    """
    Resolve food item nutrition by priority: IFCT → USDA → LLM estimate.
    On match, override item's calories/macros and set source appropriately.
    
    Args:
        item: from MealItemCreateSerializer (has item_name, serving_size_grams, 
              quantity, unit, calories, protein_g, etc., and optional source)
    
    Returns:
        item (dict) with potentially overridden macros and updated source
    """
```

Implementation:
1. Try IFCT: `ifct_match = lookup_ifct(item["item_name"])`. If match, proceed to step 4.
2. Else, try USDA: `usda_match = lookup_usda(item["item_name"])`. If match, proceed to step 4.
3. Else, return item unmodified (keep LLM estimate, source stays as-is or defaults to "llm_estimate").
4. **Scale matched data by serving size**:
   - If the match has per-100g nutrition and `serving_size_grams` is not None and > 0:
     ```python
     scale_factor = serving_size_grams / 100.0
     item["calories"] = match["calories_per_100g"] * scale_factor
     item["protein_g"] = match["protein_g_per_100g"] * scale_factor
     # etc. for carbs, fats, fiber
     ```
   - Else if `unit` is a weight unit ("g", "kg", "oz", "lb") and `quantity` is parseable to grams:
     - Attempt the same scaling (optional, more complex; see Pitfalls).
   - **Else**: skip the override (don't blindly scale against unknown units like "cups" or "servings"). Log a warning: "Cannot scale [food_name]: unknown serving size and non-weight unit [unit]."
5. Set `item["confidence"] = max(item.get("confidence", 0.85), 0.90)` — matched data is more authoritative.
6. Set `item["source"] = match["source"]` ("ifct" or "usda_fdc").
7. Return item.

### New data file: `meals/data/ifct_foods.json`

A JSON array of Indian foods with per-100g nutrition, plus aliases for fuzzy matching.

```json
[
  {
    "item_name": "Rice, white, cooked",
    "aliases": ["rice", "white rice", "basmati", "jasmine"],
    "calories_per_100g": 130,
    "protein_g_per_100g": 2.7,
    "carbs_g_per_100g": 28.0,
    "fats_g_per_100g": 0.3,
    "fiber_g_per_100g": 0.4,
    "source_detail": "IFCT 2017, NIN (Longvah et al.)"
  },
  {
    "item_name": "Daal (Red lentils), cooked",
    "aliases": ["daal", "dal", "lentils", "red lentils", "masoor"],
    "calories_per_100g": 101,
    "protein_g_per_100g": 9.0,
    "carbs_g_per_100g": 18.0,
    "fats_g_per_100g": 0.3,
    "fiber_g_per_100g": 6.5,
    "source_detail": "IFCT 2017, NIN (Longvah et al.)"
  },
  {
    "item_name": "Roti (Wheat), plain",
    "aliases": ["roti", "chapati", "wheat bread", "flatbread"],
    "calories_per_100g": 283,
    "protein_g_per_100g": 11.0,
    "carbs_g_per_100g": 58.0,
    "fats_g_per_100g": 1.0,
    "fiber_g_per_100g": 8.5,
    "source_detail": "IFCT 2017, NIN (Longvah et al.)"
  },
  {
    "item_name": "Paneer (Indian cheese), plain",
    "aliases": ["paneer", "cottage cheese", "chenna"],
    "calories_per_100g": 265,
    "protein_g_per_100g": 25.0,
    "carbs_g_per_100g": 1.2,
    "fats_g_per_100g": 20.0,
    "fiber_g_per_100g": 0,
    "source_detail": "IFCT 2017, NIN (Longvah et al.)"
  }
]
```

**Seed carefully**: include only a small curated set (10–100 entries) of **common Indian foods** with **sourced per-100g values** (cite IFCT 2017 via Longvah et al. or NIN). Do not invent nutrition data. As the system is used, expand this set responsibly with properly sourced entries.

**Future expansion**: the implementing session and future contributors should add entries methodically, citing sources (IFCT 2017, USDA FDC, peer-reviewed nutrition tables, etc.). Quality > quantity.

### Wiring into meal assembly

**File**: `meals/services/meal_service.py`, function `_assemble_meal` (lines 128–181)

Insert the lookup step **immediately after** building `validated` and **before** calling `validate_macros`:

```python
# Around line 143, change from:
#   result = validate_macros(validated)
# To:

from .food_lookup_service import resolve_item_macros

validated = [resolve_item_macros(v) for v in validated]
result = validate_macros(validated)
```

This shared insertion point ensures all three input methods (voice, text, image) apply the lookup. No other changes to `_assemble_meal` are needed.

### Configuration additions

**File**: `meal_system/settings.py` (around line 147, with other API settings)

Add after the NVIDIA settings block:

```python
# USDA FoodData Central (nutrition lookup)
USDA_API_KEY = os.environ.get('USDA_API_KEY', '')
USDA_API_BASE_URL = os.environ.get('USDA_API_BASE_URL', 'https://api.nal.usda.gov/fdc/v1')
```

**File**: `.env.example` (with other API keys)

Add:

```bash
# USDA FoodData Central API
USDA_API_KEY=demo_key  # Get a real key from fdc.nal.usda.gov after account signup
USDA_API_BASE_URL=https://api.nal.usda.gov/fdc/v1
```

### Documentation updates

**File**: `CLAUDE.md`, Backend Structure section (around line 291)

Add `food_lookup_service.py` to the services list:
```
│   ├── services/
│   │   ├── nutrition_service.py       # validate_macros()
│   │   ├── llm_service.py             # parse_meal() — Groq Llama
│   │   ├── food_lookup_service.py     # [NEW] IFCT + USDA FDC lookup
│   │   ├── whisper_service.py         # transcribe() — NVIDIA Parakeet
│   │   └── meal_service.py            # Business logic: create_meal_from_audio(), replace_meal_items(), etc.
```

Also document the new env vars (search for "## Environment Variables") and note that USDA_API_KEY should never be logged.

**File**: `docs/remove-usda-dependency-prompt.md` (append at the end, before the final section close)

Add a note acknowledging this new prompt:

```markdown

---

## Note: USDA/IFCT Lookup Reintroduced (2026-09-11)

As of this session date, a new approach to nutrition lookup has been implemented
via `docs/add-usda-ifct-nutrition-lookup-prompt.md`. Rather than a bulk-seeded
collection (the anti-pattern that prompted this document's removal of USDA
lookup), the new design uses:

- **USDA FDC API calls on-demand** (live HTTP, no bulk CSV, minimal overhead)
- **IFCT as a curated bundled dataset** (~100–500 common Indian foods, not
  multi-GB, not seeded at startup)
- The same `MealItem.source` field to track "ifct", "usda_fdc", or "llm_estimate"
- The same pattern as the removed design: on match, override LLM macros with
  authoritative data; on no match, keep LLM estimate

This avoids the seeding/maintenance pitfalls documented here while recovering
the accuracy benefits of external nutrition data. The new prompt document
should be consulted if further nutrition-lookup changes are needed.
```

---

## Rules You Must Preserve

1. **No lookup on user-edited items (PATCH)**: The `replace_meal_items()` function (`meal_service.py:233–288`) must NOT call `resolve_item_macros()`. Users editing their own recorded meals should not have their numbers silently overridden. Log a note in the function explaining this decision (e.g., "User-authored edits are trusted as-is; no re-lookup").

2. **Source field always set**: Every saved MealItem must have `source` ∈ {"ifct", "usda_fdc", "llm_estimate"}. Never allow it to be None in the DB. The default in `_assemble_meal` (line 177) is already `item_data.get("source") or "llm_estimate"` — preserve this.

3. **No exceptions from lookup**: Both `lookup_ifct()` and `lookup_usda()` must return None on any error (API timeout, JSON parse failure, malformed response, network issue) and log a warning. They must **never raise an exception** or halt meal creation. Resilience: a failed lookup falls back to LLM estimate gracefully.

4. **Parameterized USDA requests**: Always use `params=` dict (e.g., `requests.get(..., params={...})`) when calling USDA API. Never interpolate `item_name` into the URL string. This prevents injection attacks (security.md §3).

5. **No secret logging**: Never log the value of `settings.USDA_API_KEY`, even during debugging. Log only "USDA API error: {exception}" or "USDA lookup for [food_name] timed out."

6. **Confidence floor on match**: Set `item["confidence"] = max(existing, 0.90)`. Matched foods from authoritative sources are more certain than LLM estimates. Do not set it lower.

7. **Serving-size scaling required**: Only override item macros if `serving_size_grams` is known and > 0, **or** if `unit` is a parseable weight unit. If neither is available, skip the override and log a warning. This prevents nonsensical scaling (e.g., scaling per-100g data against "2 cups" with no cup-size assumption).

---

## Known Pitfalls

**Q: The IFCT dataset is tiny (4 seed entries). Will most foods match?**  
A: No — most foods will not match the bundled IFCT set or USDA. This is expected and acceptable. Unmatched items fall back to LLM, exactly as today. Over time, curate the IFCT JSON with more entries as they are sourced responsibly (not fabricated). If accuracy becomes a pain point, expand the dataset or implement caching of USDA hits.

**Q: What if the user inputs "2 cups of rice" but serving_size_grams is None?**  
A: `resolve_item_macros` will skip the override (log a warning: "Cannot scale rice: unknown serving size and non-weight unit cups"). The LLM's estimate will be used. This is better than guessing a cup size. To improve this, either (a) enhance the LLM prompt to always extract `serving_size_grams` in grams, or (b) add a unit-conversion helper for common units ("1 cup rice ≈ 185g", etc.) — out of scope for this task.

**Q: USDA API rate limits exceeded. Meals start failing?**  
A: Meal creation does NOT fail. The lookup just returns None (logged at debug level), and LLM fallback kicks in. If this becomes common, implement caching of USDA hits (see Optional Enhancements). For testing, use `DEMO_KEY` (rate limit ~30/hr); production deployments should get a real key (1000/hr).

**Q: A user uploads a meal, then edits it via PATCH. Should the new items get re-looked-up?**  
A: No. The PATCH flow (`replace_meal_items`) must NOT call `resolve_item_macros()`. User-authored edits are trusted as-is. Only LLM-parsed items (from voice/text/image) go through lookup.

**Q: What if IFCT and USDA disagree (e.g., different calories for rice)?**  
A: IFCT takes priority (designed for Indian foods, and regional variants matter). If a food appears in IFCT, USDA is not queried. If a food is not in IFCT but is in USDA, USDA is used. This is a deterministic priority, not a conflict-resolution algorithm.

**Q: I want to expand the IFCT dataset. Where do I find reliable data?**  
A: The Indian Council of Medical Research (ICMR) publishes IFCT, which is the canonical source. The Longvah et al. 2017 publication (IFCT 2017) is freely available. Verify any new entries by cross-referencing the original tables or peer-reviewed nutrition papers. Do not scrape uncited data from websites.

**Q: Confidence suddenly jumped to 0.90+ for items I'm tracking. Why?**  
A: If a food matches IFCT or USDA, its confidence is floored at 0.90 (authoritative data is more certain). This is intentional. If this affects your tracking/alerts, ensure matched foods are actually authoritative (check the `source` field in the API response).

**Q: The LLM already estimates macros. Why add lookup overhead?**  
A: LLM estimates can drift or hallucinate for common foods. Authoritative databases (USDA, IFCT) are curated by nutrition experts and are stable across time. For a tracking app where accuracy matters, combining both (lookup with LLM fallback) is a pragmatic trade-off. Overhead is minimal: IFCT is a local JSON file (~1ms lookup), USDA is cached (~5s on first hit, then cached), and failures degrade gracefully to LLM.

---

## Testing & Verification Checklist

### Unit tests: new file `tests/test_food_lookup_service.py`

- [ ] `test_lookup_ifct_exact_match()` — query "rice", expect IFCT match with per-100g calories
- [ ] `test_lookup_ifct_alias_match()` — query "daal", expect match via alias (case-insensitive)
- [ ] `test_lookup_ifct_no_match()` — query "xyz_nonexistent_food", expect None
- [ ] `test_lookup_usda_valid_response()` — mock requests.get, expect USDA match with calories_per_100g
- [ ] `test_lookup_usda_no_match()` — mock USDA empty results, expect None
- [ ] `test_lookup_usda_timeout()` — mock timeout exception, expect None + warning log (no raise)
- [ ] `test_lookup_usda_invalid_json()` — mock non-JSON response, expect None + warning log
- [ ] `test_resolve_item_macros_ifct_priority()` — mock IFCT and USDA matches, expect IFCT chosen
- [ ] `test_resolve_item_macros_ifct_then_usda()` — mock IFCT no-match but USDA match, expect USDA chosen
- [ ] `test_resolve_item_macros_scaling_with_serving_size_grams()` — pass item with serving_size_grams=200, expect macros scaled to 200g
- [ ] `test_resolve_item_macros_no_serving_size_grams()` — pass item with serving_size_grams=None and unit="cups", expect no override + warning log
- [ ] `test_resolve_item_macros_confidence_floor()` — pass item with confidence=0.70 + IFCT match, expect confidence raised to 0.90
- [ ] `test_resolve_item_macros_source_tag()` — verify source is set to "ifct"/"usda_fdc"/"llm_estimate" as appropriate

### Integration tests: update `tests/test_meal_service.py`

- [ ] `test_create_meal_from_audio_with_ifct_match()` — mock audio transcription, mock Groq to return rice+daal, expect IFCT lookups, verify saved items have source="ifct"
- [ ] `test_create_meal_from_text_with_usda_match()` — mock Groq to return "banana", mock USDA match, verify saved item has source="usda_fdc"
- [ ] `test_create_meal_from_audio_with_llm_fallback()` — mock Groq to return nonsense food, mock both IFCT and USDA no-match, verify saved item has source="llm_estimate"
- [ ] `test_replace_meal_items_no_lookup()` — PATCH a meal with new items, verify `source` is set to "llm_estimate" (lookup not called, user edits not resolved)
- [ ] `test_macro_validation_post_lookup()` — ensure `validate_macros()` still runs after lookup and catches arithmetic errors

### Security & API tests

- [ ] `test_usda_api_uses_params_dict()` — verify that the USDA call uses `params=` (not URL interpolation) by checking mock call args
- [ ] `test_usda_api_key_not_logged()` — run a USDA lookup, check logs, verify `USDA_API_KEY` never appears in output
- [ ] `test_usda_request_timeout()` — mock `requests.get` to raise `requests.Timeout`, verify no exception propagates, meal creation succeeds

### Manual/integration tests

- [ ] Set `USDA_API_KEY=demo_key` and `USDA_API_BASE_URL=https://api.nal.usda.gov/fdc/v1` in `.env`
- [ ] POST `/meals/voice` or `/meals/text` with a description like "I ate a bowl of rice and daal"
- [ ] Verify response includes `meal_items` with:
  - One item with `source="ifct"` (rice or daal, whichever matched IFCT)
  - Possibly another with `source="ifct"` or `"llm_estimate"` depending on IFCT coverage
  - Confidence ≥0.90 for matched items
- [ ] Verify unrecognized foods still have `source="llm_estimate"`
- [ ] PATCH the meal with new items (e.g., "add banana"); verify new items don't trigger re-lookup (stay as entered or LLM-estimated)
- [ ] Check server logs: no USDA_API_KEY secrets logged

### Code quality

- [ ] Run `pytest tests/test_food_lookup_service.py tests/test_meal_service.py -v` — all tests pass
- [ ] Run `pytest --cov=meals/services/food_lookup_service` — coverage > 80%
- [ ] `python -m black meals/services/food_lookup_service.py` (auto-format)
- [ ] `python -m flake8 meals/services/food_lookup_service.py` (lint, no issues)
- [ ] Verify `meals/data/ifct_foods.json` is valid JSON (`python -m json.tool meals/data/ifct_foods.json > /dev/null`)

### Backward compatibility

- [ ] Existing meals in the DB (created before this task) continue to work; no DB migration needed (`source` field already exists)
- [ ] Old cached items with `source=None` remain functional (they won't be looked up again, but existing data is not deleted)
- [ ] If a deployment has no `USDA_API_KEY` set, meals still save (lookup returns None, falls back to LLM gracefully)

---

## Sources & References

- **Prior removal doc**: `docs/remove-usda-dependency-prompt.md` — documents why USDA lookup was removed and explicitly recommends an API-based approach if revisited
- **IFCT data source**: Longvah et al. (2017). "Indian Food Composition Tables." National Institute of Nutrition, ICMR
- **USDA FDC API**: https://fdc.nal.usda.gov/api-guide.html (documentation, includes rate limits and demo key info)
- **Current architecture**: `meals/services/meal_service.py` (orchestration), `meals/models.py` (schema), `meals/serializers.py` (validation)
- **Security rules**: `.claude/rules/security.md` § 3 (parameterized queries, secret handling)

---

## Summary

This task adds on-demand nutrition lookup (USDA FDC API + IFCT curated dataset) to the meal-tracking system, improving accuracy for common and Indian foods without the multi-GB data-seeding overhead that was rejected in 2026-09-07.

**Files to create**:
1. `meals/services/food_lookup_service.py` — three functions: `lookup_ifct()`, `lookup_usda()`, `resolve_item_macros()`
2. `meals/data/ifct_foods.json` — curated JSON of Indian foods (seed with ~4–10 entries)

**Files to modify**:
1. `meals/services/meal_service.py:143` — insert lookup step before macro validation
2. `meal_system/settings.py:147` — add USDA config vars
3. `.env.example` — document USDA_API_KEY and USDA_API_BASE_URL
4. `CLAUDE.md` — document `food_lookup_service.py` and new env vars
5. `tests/test_food_lookup_service.py` — new test suite (mocked USDA, IFCT fixture)
6. `tests/test_meal_service.py` — update meal-creation tests to verify source tracking
7. `docs/remove-usda-dependency-prompt.md` — append a note pointing to this new design

**Key design decisions**:
- IFCT priority over USDA (better for Indian foods)
- Lookup only on LLM-parsed meals, never on user edits (PATCH)
- No exceptions; failures degrade gracefully to LLM fallback
- Parameterized USDA requests; no secret logging
- Confidence floored at 0.90 on match (authoritative data)
- Serving-size scaling required (no blind scaling against unknown units)
- Source tracking: "ifct" / "usda_fdc" / "llm_estimate"

**Acceptance**: All tests pass, manual meal creation shows correct source tagging, no secrets in logs, no regression in PATCH edits.

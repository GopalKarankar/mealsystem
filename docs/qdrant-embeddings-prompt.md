# Qdrant Embeddings Integration — Dev Prompt

**Purpose**: You are extending, debugging, or modifying the meal-search embedding pipeline in this FastAPI/MongoDB/Qdrant codebase. This prompt describes exactly how the Qdrant vector DB and NVIDIA NIM embeddings are wired into the application.

---

## End-to-End Flow

### 1. Startup (backend/main.py)

When the FastAPI app starts:
```python
# Line 9-10 in main.py
client.admin.command("ping")                    # Verify MongoDB connection
ensure_qdrant_collection()                      # Bootstrap or verify Qdrant collection
```

### 2. Qdrant Bootstrap (backend/app/database.py)

The `ensure_qdrant_collection()` function:
- Checks if the collection already exists via `qdrant_client.get_collection(settings.qdrant_collection_name)`
- If missing, creates it with:
  - **Vector size**: `settings.embedding_vector_size` (default: `2048`)
  - **Distance metric**: `Distance.COSINE` (for semantic similarity)
  - **Collection name**: `settings.qdrant_collection_name` (default: `"meals"`)

```python
qdrant_client = QdrantClient(
    url=settings.qdrant_url,                    # e.g., http://localhost:6333
    api_key=settings.qdrant_api_key if settings.qdrant_api_key else None
)

def ensure_qdrant_collection():
    try:
        qdrant_client.get_collection(settings.qdrant_collection_name)
    except Exception:
        qdrant_client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_vector_size,    # MUST match embedding model output dimension
                distance=Distance.COSINE
            )
        )
```

**Critical invariant**: `settings.embedding_vector_size` must always equal the output dimension of `settings.embedding_model`. If you change the embedding model, you MUST also update `embedding_vector_size`, or upserts will fail. If they diverge, drop the collection and let it recreate: `docker exec meal-qdrant sh -c "curl -X DELETE http://localhost:6333/collections/meals"`.

---

## 3. Embedding Service (backend/app/services/embedding_service.py)

All embeddings go through `embed_text()`:

```python
def embed_text(text: str, input_type: str = "passage") -> list[float]:
    """Embed text using NVIDIA's nemotron-3-embed-1b model (via NVIDIA NIM cloud API)."""
    resp = _client.embeddings.create(
        model=settings.embedding_model,         # "nvidia/nemotron-3-embed-1b"
        input=text,
        extra_body={"input_type": input_type, "truncate": "END"},
    )
    return resp.data[0].embedding
```

**Key detail**: The `input_type` parameter is **critical**:
- `input_type="passage"` when embedding stored/indexed content (meal transcripts, text being inserted/updated)
- `input_type="query"` when embedding search queries (user's search text)

**Mismatching these silently degrades search quality** — the embeddings will be in the same vector space but not optimally aligned. No error is thrown; results just won't match well.

The embedding model uses `openai.OpenAI` client pointed at NVIDIA NIM:
- `api_key=settings.nvidia_api_key` (required, no default)
- `base_url=settings.nvidia_api_base_url` (default: `https://integrate.api.nvidia.com/v1`)

---

## 4. Create Meal (Embed + Upsert)

When a user POSTs audio to `/meals/voice`:

**Route** (`backend/app/routes/meals.py:23`):
```python
@router.post("/voice", response_model=MealResponse, status_code=status.HTTP_201_CREATED)
def create_meal_voice(file: UploadFile = File(...), ...):
    # Validate, save temp audio, then call:
    meal = meal_service.create_meal_from_audio(current_user["_id"], temp_path, db)
```

**Service** (`backend/app/services/meal_service.py:80`):
```python
def create_meal_from_audio(user_id, audio_path: str, db) -> dict:
    transcript = whisper_service.transcribe(audio_path)      # Groq Whisper
    raw_items = llm_service.parse_meal(transcript)           # Groq Llama
    # ... validation, macro correction ...
    
    meal_doc = {
        "user_id": user_id,
        "original_text": transcript,                          # Raw voice transcript
        "transcription_text": transcript,
        "created_at": datetime.utcnow(),
        "confidence_score": confidence_score,
        "meal_items": [/* list of MealItem dicts */],
    }
    
    result = db.meals.insert_one(meal_doc)                   # Insert into MongoDB
    meal_doc["_id"] = result.inserted_id
    
    # Index in Qdrant for semantic search
    try:
        vector = embedding_service.embed_text(transcript, input_type="passage")
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=[PointStruct(
                id=str(meal_doc["_id"]),                      # Qdrant point ID = Mongo ObjectId as string
                vector=vector,                                # 2048-dim vector
                payload={"mongo_meal_id": str(meal_doc["_id"]), "user_id": str(user_id)},
            )],
        )
    except Exception:
        logger.exception("Failed to index meal in Qdrant (search will not find it, meal still saved)")
    
    return meal_doc
```

**Invariants**:
- Point ID in Qdrant **must always equal** `str(meal["_id"])` (Mongo ObjectId converted to string)
- Payload **must always include** `mongo_meal_id` and `user_id` (needed for search filtering and lookup)
- Meal is inserted into Mongo **before** trying to index in Qdrant, so if embedding fails, the meal still exists (but won't be searchable)

---

## 5. Update Meal (Re-embed + Re-upsert)

When a user PATCHes meal items at `PATCH /meals/{meal_id}`:

**Route** (`backend/app/routes/meals.py:125`):
```python
@router.patch("/{meal_id}", response_model=MealResponse)
def update_meal(meal_id: str, payload: MealUpdate, ...):
    meal = db.meals.find_one({"_id": oid})
    meal = meal_service.replace_meal_items(meal, payload, db)
```

**Service** (`backend/app/services/meal_service.py:158`):
```python
def replace_meal_items(meal: dict, payload: MealUpdate, db) -> dict:
    # ... validation, macro correction ...
    
    new_items = [/* corrected MealItem list */]
    
    update_fields = {
        "meal_items": new_items,
        "confidence_score": confidence_score,
        "updated_at": datetime.utcnow()
    }
    if payload.original_text:
        update_fields["original_text"] = payload.original_text
    
    db.meals.update_one({"_id": meal["_id"]}, {"$set": update_fields})  # Update Mongo
    meal.update(update_fields)
    
    # Re-index in Qdrant with updated text
    try:
        text_to_embed = payload.original_text or meal.get("original_text", "")
        vector = embedding_service.embed_text(text_to_embed, input_type="passage")
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=[PointStruct(
                id=str(meal["_id"]),                          # Same ID as original
                vector=vector,                                # New vector from updated text
                payload={"mongo_meal_id": str(meal["_id"]), "user_id": str(meal["user_id"])},
            )],
        )
    except Exception:
        logger.exception("Failed to re-index meal in Qdrant after update")
    
    return meal
```

**Invariants**:
- The Qdrant point ID stays the same (Mongo `_id`), so the upsert replaces the old vector with the new one
- If `payload.original_text` is provided, use it; otherwise fall back to the existing `original_text` in the meal doc
- Mongo is updated **before** re-indexing in Qdrant (if Qdrant fails, Mongo still has the new data)

---

## 6. Delete Meal (Sync Mongo + Qdrant)

When a user DELETEs a meal at `DELETE /meals/{meal_id}`:

**Route** (`backend/app/routes/meals.py:164`):
```python
@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal(meal_id: str, ...):
    oid = ObjectId(meal_id)
    meal = db.meals.find_one({"_id": oid})
    
    db.meals.delete_one({"_id": oid})                         # Delete from Mongo
    
    # Delete from Qdrant
    try:
        qdrant_client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=[str(oid)]                        # Pass Mongo _id as string
        )
    except Exception:
        logger.exception("Failed to delete meal from Qdrant")
```

**Invariant**: Mongo and Qdrant deletions must stay in sync. If Qdrant delete fails (e.g., network issue), log it but don't roll back the Mongo delete — the meal is gone, just won't be removed from the vector DB until manual cleanup.

---

## 7. Search (Embed Query + Fetch Results)

When a user calls `GET /meals/search?q=...`:

**Route** (`backend/app/routes/meals.py:103`):
```python
@router.get("/search", response_model=List[MealResponse])
def search_meals(q: str = Query(..., min_length=1), limit: int = Query(10), ...):
    """Search meals by semantic similarity to query text."""
    meal_ids = meal_service.semantic_search_meal_ids(q, current_user["_id"], limit)
    meals = []
    for mid in meal_ids:
        oid = ObjectId(mid)
        meal = db.meals.find_one({"_id": oid})
        if meal:
            meals.append(meal)
    return [meal_service.serialize_meal(m) for m in meals]
```

**Service** (`backend/app/services/meal_service.py:262`):
```python
def semantic_search_meal_ids(query_text: str, user_id, limit: int) -> list[str]:
    """Search for meals by semantic similarity to query text."""
    try:
        vector = embedding_service.embed_text(query_text, input_type="query")  # QUERY, not passage
        hits = qdrant_client.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=vector,
            query_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))]),
            limit=limit,
        )
        return [h.payload["mongo_meal_id"] for h in hits]      # Extract Mongo IDs
    except Exception:
        logger.exception("Failed to search Qdrant")
        return []
```

**Invariants**:
- Query text must be embedded with `input_type="query"` (not `"passage"`)
- Results **must** be filtered by `user_id` — never return another user's meals
- Return Mongo `_id` strings from `h.payload["mongo_meal_id"]`, then fetch full docs from Mongo (Qdrant only stores IDs + user_id in payload, not full meal data)

---

## Configuration Fields

**In `backend/app/config.py`** (pydantic-settings):

| Field | Env Var | Default | Notes |
|-------|---------|---------|-------|
| `qdrant_url` | `QDRANT_URL` | `http://localhost:6333` | Qdrant server endpoint |
| `qdrant_api_key` | `QDRANT_API_KEY` | (empty) | Leave blank for local Docker; set for Qdrant Cloud |
| `qdrant_collection_name` | `QDRANT_COLLECTION_NAME` | `"meals"` | Collection name (must match across bootstrap & operations) |
| `nvidia_api_key` | `NVIDIA_API_KEY` | (required, no default) | Get from https://build.nvidia.com |
| `nvidia_api_base_url` | `NVIDIA_API_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA NIM API endpoint |
| `embedding_model` | `EMBEDDING_MODEL` | `"nvidia/nemotron-3-embed-1b"` | Embedding model name |
| `embedding_vector_size` | `EMBEDDING_VECTOR_SIZE` | `2048` | **MUST match model output dimension** |

**Dependencies in `requirements.txt`**:
- `qdrant-client==1.12.1`
- `openai==1.54.0` (used as client for NVIDIA NIM)

---

## Rules You Must Preserve

1. **Mongo ↔ Qdrant Sync**: Any meal write to Mongo (create/update/delete) must have a matching Qdrant operation in the same code path. Never let the stores drift.

2. **Point ID Invariant**: Qdrant point ID must **always** equal `str(meal["_id"])` (Mongo ObjectId as string). This allows join-back lookup from search results.

3. **Vector Dimension Mismatch**: If you change `embedding_model` (e.g., to a different NVIDIA model or another provider), update `embedding_vector_size` to match the new model's output dimension. Dimension mismatch causes upsert failures.
   - **Recovery**: Drop the collection (`curl -X DELETE http://localhost:6333/collections/meals`), restart the backend (which will recreate it), then re-embed all meals.

4. **input_type Correctness**: Always use `input_type="passage"` when indexing stored content, and `input_type="query"` when embedding search queries. Mismatching silently breaks search quality.

5. **User ID Filtering**: All search operations **must** filter by `user_id` in the Qdrant query filter. Never return another user's meals, even if they have the same keywords.

6. **Payload Structure**: Qdrant `PointStruct.payload` must always include `mongo_meal_id` and `user_id`. The search route depends on these to join back to Mongo and filter results.

---

## Known Pitfalls

- **Collection doesn't exist on startup**: If `ensure_qdrant_collection()` is never called or Qdrant is unreachable, the app starts but indexing will fail with "collection not found". Check: (1) Is `ensure_qdrant_collection()` called in `main.py` before creating the app? (2) Is Qdrant running? (3) Is `QDRANT_URL` pointing to the right place?

- **Vector dimension mismatch after model swap**: If you swap `EMBEDDING_MODEL` to use a different vector size but forget to update `EMBEDDING_VECTOR_SIZE`, upserts will fail with "vector size mismatch". Symptom: meals save to Mongo but don't appear in search results, logs show Qdrant upsert errors.

- **Stale collection after provider migration**: If you switch from (e.g.) OpenAI embeddings to NVIDIA NIM, the old vectors have different semantics. The old collection becomes useless. Drop it and recreate.

- **Search returns nothing**: Check (1) Is `input_type="query"` used? (2) Does the meal actually exist in Qdrant (check `POST /meals/voice` succeeded without Qdrant error logs)? (3) Is `user_id` in the filter correct?

- **Mongo and Qdrant out of sync**: After a crash or network failure, they may diverge. Check: `db.meals.count()` vs. `qdrant_client.get_collection(settings.qdrant_collection_name).points_count`. If they differ, either manually sync or re-index all meals.

---

## Quick Reference: When to Embed

| Operation | Code Path | input_type | Happens When |
|-----------|-----------|-----------|--------------|
| Create meal from voice | `create_meal_from_audio()` | `"passage"` | User POSTs audio, transcript extracted |
| Update meal text | `replace_meal_items()` | `"passage"` | User PATCHes meal items or description |
| Search meals | `semantic_search_meal_ids()` | `"query"` | User calls `GET /meals/search?q=...` |

---

## How to Add a New Embedding Feature

If you need to add another text field to meals (e.g., "notes"), or change what gets indexed:

1. **Identify the text field** that should be searchable (e.g., `meal_items[].notes`)
2. **Aggregate it into a string** at index time (e.g., `" ".join([item["notes"] for item in meal_items])`)
3. **Embed with `input_type="passage"`** in the upsert code path
4. **No payload change needed** — Qdrant payload only needs `mongo_meal_id` and `user_id` for filtering and join-back
5. **Search still queries the full vector** (Qdrant doesn't index individual fields separately)

Example: To make notes searchable:
```python
# In create_meal_from_audio() or replace_meal_items():
notes_text = " ".join([item.get("notes", "") for item in meal_items if item.get("notes")])
full_text = f"{transcript} {notes_text}"  # Concatenate for semantic search
vector = embedding_service.embed_text(full_text, input_type="passage")
```

---

## Testing Checklist

- [ ] Qdrant running locally (`docker ps | grep qdrant`)
- [ ] `NVIDIA_API_KEY` set in `backend/.env`
- [ ] `POST /meals/voice` succeeds and logs show no Qdrant errors
- [ ] Meal appears in `GET /meals?date=...` result
- [ ] `GET /meals/search?q=...` returns results (semantic match on transcript)
- [ ] `PATCH /meals/{id}` updates Mongo and re-indexes in Qdrant
- [ ] `DELETE /meals/{id}` removes from both Mongo and Qdrant
- [ ] No cross-user leakage: user A searches, only gets user A's meals
- [ ] Collection bootstrap on app startup: restart backend, no "collection not found" errors


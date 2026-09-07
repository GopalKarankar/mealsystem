import re
from uuid import uuid4

def generate_unique_username(local_part: str, db) -> str:
    base = re.sub(r'[^a-zA-Z0-9_]', '_', local_part)
    base = re.sub(r'_+', '_', base).strip('_')

    if len(base) < 3:
        base = f"user_{base}"

    base = base[:45]

    if not db.users.find_one({"username": base}):
        return base

    for n in range(2, 51):
        candidate = f"{base}_{n}"
        if not db.users.find_one({"username": candidate}):
            return candidate

    return f"{base}_{uuid4().hex[:8]}"

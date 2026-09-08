import re
from uuid import uuid4
from .models import User


def generate_unique_username(local_part: str) -> str:
    """Generate a unique username from an email local part."""
    base = re.sub(r'[^a-zA-Z0-9_]', '_', local_part)
    base = re.sub(r'_+', '_', base).strip('_')

    if len(base) < 3:
        base = f"user_{base}"

    base = base[:45]

    if not User.objects.filter(username=base).exists():
        return base

    for n in range(2, 51):
        candidate = f"{base}_{n}"
        if not User.objects.filter(username=candidate).exists():
            return candidate

    return f"{base}_{uuid4().hex[:8]}"

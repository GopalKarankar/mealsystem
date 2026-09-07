# Meal Ingestion Pipeline - Voice-to-Structured Nutrition Data

A full-stack application where users log meals via voice input and get instant macro nutrient data through AI parsing.

**Tech Stack**: React 19 + Vite | FastAPI + SQLAlchemy | Groq Whisper-large-v3 + Groq Llama-3.3-70B

**Deadline**: September 12, 2026

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.10+
- Git

### Frontend Setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Visit: http://localhost:5173

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

API Docs: http://localhost:8000/docs

## Project Structure

```
meal-system/
├── frontend/                 # React + Vite + Tailwind
│   ├── src/components/       # UI components
│   ├── src/pages/            # Page components
│   ├── src/store/            # Zustand state management
│   └── src/utils/            # Helper functions
├── backend/                  # FastAPI
│   ├── app/
│   │   ├── auth/             # JWT authentication
│   │   ├── routes/           # API endpoints
│   │   └── services/         # Business logic
│   └── main.py               # FastAPI app entry
└── CLAUDE.md                 # Specification & Development Guide
```

## Common Commands

**Frontend**:
- `npm run dev` — Start dev server
- `npm run build` — Production build
- `npm run lint` — Check code
- `npm run format` — Auto-format

**Backend**:
- `python main.py` — Start API server
- `pytest` — Run tests
- `python -m pytest tests/ -v` — Verbose test output

## API Quick Reference

**Auth**:
- `POST /auth/register` — Create account
- `POST /auth/login` — Get JWT token

**Meals**:
- `POST /meals/voice` — Upload audio, parse meal
- `GET /meals` — List user's meals
- `PATCH /meals/{id}` — Edit meal
- `DELETE /meals/{id}` — Delete meal
- `GET /dashboard` — Daily summary

See full spec in [CLAUDE.md](./CLAUDE.md) sections 5 & 8.

## Environment Variables

Create `.env` files in `frontend/` and `backend/` from `.env.example`.

**Critical for backend**:
- `SECRET_KEY` — Change for production
- `GROQ_API_KEY` — Groq API (get free key from console.groq.com)

## Development Guidelines

- Follow design tokens in `frontend/src/styles/variables.css`
- Keep components under 300 LOC
- Use Pydantic schemas for request/response validation
- All API responses use consistent JSON structure
- See [CLAUDE.md](./CLAUDE.md) for full architecture details

## Testing

```bash
# Frontend
npm test

# Backend
cd backend
pytest tests/
pytest tests/test_auth.py -v
pytest tests/test_voice.py -v
```

## Deployment

See [CLAUDE.md](./CLAUDE.md) section 15 for full checklist.

**Quick checklist**:
- [ ] No console.logs / debug statements
- [ ] Linted and formatted
- [ ] Tests passing
- [ ] Environment variables documented
- [ ] Database migrations included

## Documentation

- **Design System**: CLAUDE.md § 3 (colors, typography, components)
- **Database**: CLAUDE.md § 4 (schema, relationships)
- **API Spec**: CLAUDE.md § 5 (endpoints, validation)
- **LLM Prompting**: CLAUDE.md § 8 (Groq Llama system/user prompts)
- **Error Handling**: CLAUDE.md § 9 (edge cases, fallbacks)
- **Accessibility**: CLAUDE.md § 11 (WCAG 2.1 AA)

## Support

For issues or questions, refer to:
1. [CLAUDE.md](./CLAUDE.md) — Full spec
2. Backend API docs: http://localhost:8000/docs (Swagger UI)
3. Frontend tests: `npm test`

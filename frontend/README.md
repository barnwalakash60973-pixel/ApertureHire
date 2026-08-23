# Aperture — AI Assignment Reviewer (Frontend)

React 19 + Vite + TypeScript + Tailwind frontend for the FastAPI assignment
review backend.

## Setup

```bash
npm install
cp .env.example .env.local   # set VITE_API_BASE_URL to your backend
npm run dev
```

## Backend contract

- `POST /api/v1/review` — multipart form with fields `question_paper` and
  `submission` (`.pdf`/`.docx`). Returns `{ report: FinalReport }`.
- `GET /api/v1/health`

See `src/types/report.ts` for the exact response shape — it mirrors
`app/domain/models.py` field-for-field.

**Note:** the backend's `FinalReport` model originally didn't declare
`score_breakdown` or `statistics`, even though `ReportBuilder` computed
both. Pydantic silently dropped them on construction. Both fields have
been added to `app/domain/models.py` — redeploy that fix alongside this
frontend or the Analytics Cards and Score Breakdown chart will render
empty.

## Deploy

Deployable as-is on Vercel: `npm run build`, output in `dist/`.

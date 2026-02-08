# Metrics Explorer – React Frontend

Simple React UI to set organization and provider, and call the Metrics Explorer APIs (dashboards, monitors, metrics).

## Setup

```bash
cd frontend
npm install
```

## Development

Start the backend first (from project root):

```bash
uvicorn app.main:app --reload
```

Then start the frontend (from `frontend/`):

```bash
npm run dev
```

Open http://localhost:3002. The Vite dev server proxies `/api` to `http://localhost:8001`, so API calls work without CORS.

## Build

```bash
npm run build
```

Output is in `dist/`. To serve it with the FastAPI app, mount the `frontend/dist` folder at `/ui` (or use a static server).

## Environment

- `VITE_API_BASE_URL` – optional; if set, API requests use this base URL (e.g. `http://localhost:8001`). If unset, relative URLs are used (works with the dev proxy).

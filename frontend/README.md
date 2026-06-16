# Training Log Frontend

React + TypeScript + Vite frontend for the Training Log app. This is the only
product UI; FastAPI serves the compiled bundle for non-API routes and exposes
the JSON API under `/api/v1`.

Runtime offline rules:

- Use same-origin `/api/v1` calls.
- Do not load scripts, styles, fonts, images, icons, charts, or API data from remote hosts.
- Bundle frontend assets into the app build before serving them from FastAPI.

Local development, once Node/npm are installed:

```bash
npm install
npm run dev
```

FastAPI should run on `http://localhost:8000`; Vite proxies `/api` to that origin.

Production build:

```bash
npm run build
```

The Docker build runs this step in a Node stage and copies `dist/` into the
Python image at `app/static`. At runtime the container only needs the local
bundle, FastAPI, and SQLite data volume.

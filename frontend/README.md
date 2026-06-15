# Training Log Frontend

React + TypeScript + Vite shell for the incremental migration.

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

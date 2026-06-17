# Training Log

Personal workout logger for Home Assistant. The app stores workout data in SQLite, serves a FastAPI backend, and builds a React frontend into the container image.

## Development

Use Python 3.12 and Node 22.

```bash
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run typecheck
npm run build
cd ..
```

For local backend runs, set `DB_PATH` if you do not want to use the default `data/training.db`.

```bash
DB_PATH=data/training.db uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Tests

```bash
python -m unittest discover -s tests
cd frontend
npm run typecheck
npm run build
```

## Docker

Build and run the container locally:

```bash
docker build -t training-log:local .
docker compose up --build
```

The compose file mounts `./data` to `/data`, and the container uses `/data/training.db`.

## Home Assistant Add-On

The add-on metadata lives in `config.yaml`. It exposes port `8000`, enables ingress at `/`, and stores runtime data at `/data/training.db` through the `DB_PATH` environment variable.

Install or update it as a local/custom add-on repository, then rebuild the add-on from Home Assistant after changes are merged.

## Runtime Data

Runtime databases, WAL/SHM files, and token files are ignored by Git. Keep backups through the app Backup page before replacing production containers or add-ons.

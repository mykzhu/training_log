---
name: training-log-home-assistant-addon
description: Use this when changing Training Log as a Home Assistant add-on, especially config.yaml, ingress/base-path behavior, static routing, Docker build, and release metadata.
---

# Training Log Home Assistant Add-on Skill

## When to use

Use for:

```text
config.yaml
Dockerfile
Home Assistant ingress
base path / URL prefix
static React routing
release version
add-on metadata
```

## Known add-on expectations

`config.yaml` should keep:

```yaml
name: Training Log
slug: training_log
ingress: true
ingress_port: 8000
webui: http://[HOST]:[PORT:8000]/
panel_title: Training Log
panel_icon: mdi:dumbbell
```

Version should be bumped only during release prep.

## Ingress / base path rules

The app must work behind Home Assistant ingress.

Frontend:

```text
React Router basename must handle runtime base path.
API calls must use same runtime base path.
Vite base should support relative assets if currently configured.
```

Backend:

```text
APP_URL_PREFIX or equivalent should strip/handle prefix.
Static routes should serve React app correctly.
Deep links should work.
```

## Static routing tests

When touching routing/base path, update tests around React static serving.

Check:

```text
/
current route
history route
stats route
garmin route
settings route
unknown route
asset paths
API paths
prefixed ingress paths
```

## Release rules

Do not bump:

```text
config.yaml version
CHANGELOG release section
```

until release phase and tests pass.

## Verification

Run:

```bash
python -m unittest discover -s tests
cd frontend
npm run typecheck
npm run build
cd ..
docker build -t training-log:<version> .
```

Manual Home Assistant smoke:

```text
Install/update add-on.
Open from sidebar.
Check top navigation.
Refresh deep link.
Open Settings.
Open Garmin.
Start workout.
```

## Do not

- Do not break ingress paths.
- Do not assume root `/` deployment only.
- Do not remove `panel_title` or `panel_icon`.
- Do not expose backend port unintentionally beyond current add-on design.

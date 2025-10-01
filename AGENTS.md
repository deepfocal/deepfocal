# Repository Guidelines

## Project Structure & Module Organization
- `deepfocal_backend/` holds Django settings, Celery config, and shared utilities; the `reviews/` app contains API views, services, topic modeling, and migrations.
- `scripts/` hosts ingestion helpers (`import_apple_reviews.py`, `import_google_reviews.py`, `analyze_reviews.py`) that run from the repo root once the Python virtualenv is active.
- `deepfocal-frontend/` houses the Vite/React dashboard with source code in `src/`, shared assets in `public/`, and build artifacts in `dist/`. Environment samples live beside each stack in `.env.*` files.

## Build, Test, and Development Commands
- Backend: `python -m venv venv`, `venv\\Scripts\\activate`, `pip install -r requirements.txt`, `python manage.py migrate`, `python manage.py runserver 0.0.0.0:8000`.
- Workers: run `celery -A deepfocal_backend worker -l info` and pair with `celery -A deepfocal_backend beat -l info` when scheduling imports.
- Frontend: from `deepfocal-frontend/` run `npm install`, `npm run dev`, `npm run build`, and `npm run preview` to verify the production bundle.

## Coding Style & Naming Conventions
- Python: follow PEP 8, use snake_case for helpers, PascalCase for models, and ALL_CAPS for constants. Prefer explicit imports, add type hints in services/tasks, and keep docstrings concise but informative.
- React: ship functional components, prefix hooks with `use`, keep component files PascalCase, and lean on Tailwind utilities before custom CSS. Run `npm run lint` before submitting UI changes.
- Configuration files (JSON/YAML/env) stay camelCase unless third-party tooling dictates otherwise.

## Testing Guidelines
- Django tests reside in app-level `tests.py`; add modules under `reviews/tests/` as coverage grows. Execute suites with `python manage.py test reviews`, and capture fixtures in `reviews/fixtures/` when deterministic data is required.
- Scripts benefit from smoke checks in a lightweight `scripts/tests/` package (create on demand) or clearly documented manual steps inside each script docstring.
- Frontend tests belong in `src/__tests__/`; wire up Vitest and run `npm test` as the surface expands.

## Commit & Pull Request Guidelines
- Commit messages should be short, imperative, and under 72 characters (e.g., `Add sentiment benchmark`). Add descriptive bodies when rationale or follow-up work needs context.
- Pull requests summarize scope, list API or schema changes, and attach screenshots for visual updates. Link Jira/GitHub issues, note new environment variables, and call out Celery worker/beat considerations for release handoffs.

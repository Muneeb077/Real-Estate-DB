# Local development shortcuts (MySQL 8+ running locally; see README).
PY := backend/.venv/bin/python

.PHONY: setup migrate seed api web test lint loadtest rotate-keys

setup:            ## install backend and frontend dependencies
	python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

migrate:          ## apply all migrations (as the migrator account)
	cd backend && .venv/bin/alembic upgrade head

seed:             ## load demo accounts + 50k listings + a year of history
	cd backend && .venv/bin/python scripts/seed.py

api:              ## run the API on :5050
	cd backend && .venv/bin/gunicorn -w 4 -b 127.0.0.1:5050 wsgi:app

web:              ## run Next.js on :3000 (proxies /api to :5050)
	cd frontend && npm run dev

test:             ## backend tests against TEST_DATABASE_URL
	cd backend && .venv/bin/pytest -q

lint:
	cd frontend && npx eslint src

loadtest:         ## 300 virtual users for 60s against the local API
	cd backend && RATELIMIT_ENABLED=false .venv/bin/locust -f loadtest/locustfile.py --host http://127.0.0.1:5050 --headless -u 300 -r 30 -t 60s

rotate-keys:      ## re-wrap all data keys under KEK_ACTIVE
	cd backend && .venv/bin/python scripts/rotate_keys.py

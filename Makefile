PORT=5000
REDIS_PORT=6379
PYTHON=. .venv/bin/activate && dotenv run --override --

.PHONY: install kill-server kill-worker kill-redis api worker docker-up docker-down migrate dev run-prod run stop

install:
	@test -d .venv || python3 -m venv .venv
	@. .venv/bin/activate && pip install -q -r requirements.txt

kill-server:
	@PID=$$(lsof -t -i:$(PORT)); \
	if [ -n "$$PID" ]; then \
		echo "Killing process on port $(PORT): $$PID"; \
		kill $$PID; \
	else \
		echo "Port $(PORT) is free."; \
	fi

kill-worker:
	@PID=$$(pgrep -f "^python3 worker\.py$$"); \
	if [ -n "$$PID" ]; then \
		echo "Stopping worker: $$PID"; \
		kill $$PID; \
	else \
		echo "Worker is not running."; \
	fi

kill-redis:
	@if systemctl is-active --quiet redis-server 2>/dev/null; then \
		echo "Stopping local redis-server to free port $(REDIS_PORT)"; \
		sudo systemctl stop redis-server; \
	else \
		echo "Port $(REDIS_PORT) is free for docker."; \
	fi

api: kill-server
	$(PYTHON) python3 run.py &

worker: kill-worker
	$(PYTHON) python3 worker.py &

docker-up:
	docker compose up -d --wait

docker-down:
	docker compose down

migrate:
	npx --yes supabase db push

dev: install kill-server kill-worker kill-redis docker-up
	$(PYTHON) gunicorn --bind 0.0.0.0:$(PORT) run:app &
	$(PYTHON) python3 worker.py &

run-prod: install kill-server kill-worker kill-redis docker-up
	. .venv/bin/activate && honcho start

run: run-prod

stop: kill-server kill-worker
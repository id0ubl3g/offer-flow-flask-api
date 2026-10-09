REDIS_PORT=6379

.PHONY: install kill-redis run stop restart logs migrate

install:
	@test -d .venv || python3 -m venv .venv
	@. .venv/bin/activate && pip install -q -r requirements.txt

kill-redis:
	@if systemctl is-active --quiet redis-server 2>/dev/null; then \
		echo "Stopping local redis-server to free port $(REDIS_PORT)"; \
		sudo systemctl stop redis-server; \
	else \
		echo "Port $(REDIS_PORT) is free for docker."; \
	fi

run: kill-redis
	docker compose up -d --build --wait

stop:
	docker compose down

restart:
	docker compose up -d --build --wait api worker

logs:
	docker compose logs -f api worker

migrate:
	npx --yes supabase db push

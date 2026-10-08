from src.extensions import get_redis
from src.services import dispatch_service

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from flask import Flask
import threading
import logging
import signal
import uuid

TICK_SECONDS = 30
LOCK_KEY = "worker:dispatcher:lock"
LOCK_TTL = 90
MAX_PARALLEL_USERS = 8

logger = logging.getLogger(__name__)

class Dispatcher:
    def __init__(self, app: Flask) -> None:
        self.app = app
        self.token = uuid.uuid4().hex
        self.stop_event = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL_USERS)
        self.active_users: set[str] = set()
        self.active_runs: set[str] = set()
        self.state_lock = threading.Lock()
        self.recovered = False

    def stop(self, *args) -> None:
        logger.info("Stopping dispatcher")
        self.stop_event.set()

    def acquire_lock(self) -> bool:
        redis = get_redis()

        if redis.set(LOCK_KEY, self.token, nx=True, ex=LOCK_TTL):
            return True

        if redis.get(LOCK_KEY) == self.token:
            redis.expire(LOCK_KEY, LOCK_TTL)
            return True

        return False

    def release_lock(self) -> None:
        redis = get_redis()

        if redis.get(LOCK_KEY) == self.token:
            redis.delete(LOCK_KEY)

    def tick(self) -> None:
        if not self.recovered:
            with self.state_lock:
                recovered = dispatch_service.recover_interrupted_runs(set(self.active_runs))

            if recovered:
                logger.warning("Marked %s interrupted runs as failed", recovered)

            self.recovered = True

        now = datetime.now(timezone.utc)

        for schedule in dispatch_service.list_active_schedules():
            with self.state_lock:
                if schedule["user_id"] in self.active_users:
                    continue

            slot = dispatch_service.due_slot(schedule, now)

            if slot is None:
                continue

            run = dispatch_service.create_run(schedule, slot)

            if run is None:
                continue

            with self.state_lock:
                self.active_users.add(schedule["user_id"])
                self.active_runs.add(run["id"])

            logger.info("Starting run %s for schedule %s at %s", run["id"], schedule["id"], slot.isoformat())
            self.executor.submit(self.execute, run, schedule)

    def execute(self, run: dict, schedule: dict) -> None:
        try:
            with self.app.app_context():
                status = dispatch_service.process_run(run, schedule, self.stop_event.wait)
                logger.info("Run %s finished with status %s", run["id"], status)

        except Exception:
            logger.exception("Run %s crashed", run["id"])

            with self.app.app_context():
                dispatch_service.fail_run(run["id"], "Run crashed")

        finally:
            with self.state_lock:
                self.active_users.discard(schedule["user_id"])
                self.active_runs.discard(run["id"])

    def run_forever(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        logger.info("Dispatcher started")

        while not self.stop_event.is_set():
            try:
                with self.app.app_context():
                    if self.acquire_lock():
                        self.tick()
                    else:
                        self.recovered = False

            except Exception:
                logger.exception("Dispatcher tick failed")

            self.stop_event.wait(TICK_SECONDS)

        self.executor.shutdown(wait=True)

        with self.app.app_context():
            self.release_lock()

        logger.info("Dispatcher stopped")
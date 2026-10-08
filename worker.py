from src.api.app import create_app
from src.worker.dispatcher import Dispatcher

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    Dispatcher(create_app()).run_forever()
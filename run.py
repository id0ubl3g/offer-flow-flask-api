from config.path_config import add_project_root_to_path
from src.api.app import Server

add_project_root_to_path()

server = Server()
app = server.app

if __name__ == "__main__":
    server.run_production()
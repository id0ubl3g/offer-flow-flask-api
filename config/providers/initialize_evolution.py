from src.services.evolution_client import EvolutionClient

from dotenv import load_dotenv
import os

load_dotenv()

def initialize_evolution() -> EvolutionClient:
    return EvolutionClient(
        os.getenv("EVOLUTION_API_URL", "http://localhost:8080"),
        os.getenv("EVOLUTION_API_KEY")
    )
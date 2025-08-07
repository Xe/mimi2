from dotenv import load_dotenv
load_dotenv()
import os

from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry

func = get_registry().get("ollama").create(name="snowflake-arctic-embed2:latest", host=os.getenv("OLLAMA_URL", "http://localhost:11434"))

class Docs(LanceModel):
    file_path: str
    section: int
    text: str = func.SourceField()
    embedding: Vector(func.ndims()) = func.VectorField()
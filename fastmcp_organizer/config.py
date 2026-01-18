import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    ROOT_DIR = Path(os.getenv("ROOT_DIR", "/data/target"))
    DB_PATH = os.getenv("DATABASE_URL", "/data/state/state.db").replace("sqlite:///", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
    
    # Observability
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    ALLOW_SYMLINKS = os.getenv("ALLOW_SYMLINKS", "false").lower() == "true"

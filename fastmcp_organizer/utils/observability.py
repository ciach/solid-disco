import logging
from langfuse import Langfuse
from fastmcp_organizer.config import Config

class Observability:
    _langfuse = None

    @classmethod
    def get_client(cls):
        if not cls._langfuse and Config.LANGFUSE_PUBLIC_KEY:
            try:
                cls._langfuse = Langfuse(
                    public_key=Config.LANGFUSE_PUBLIC_KEY,
                    secret_key=Config.LANGFUSE_SECRET_KEY,
                    host=Config.LANGFUSE_HOST
                )
            except Exception as e:
                logging.warning(f"Failed to initialize Langfuse: {e}")
        return cls._langfuse

    @staticmethod
    def track_event(name: str, metadata: dict = None):
        logging.info(f"EVENT: {name} | {metadata}")
        client = Observability.get_client()
        if client:
            try:
                client.create_event(name=name, metadata=metadata)
            except Exception as e:
                logging.warning(f"Langfuse error: {e}")

    @staticmethod
    def flush():
        client = Observability.get_client()
        if client:
            try:
                client.flush()
            except Exception as e:
                logging.warning(f"Langfuse flush error: {e}")

    @staticmethod
    def trace(name: str, **kwargs):
        """Returns a context manager for a trace/span"""
        client = Observability.get_client()
        if client:
            return client.start_as_current_span(name=name, **kwargs)
    @staticmethod
    def generation(name: str, **kwargs):
        """Returns a context manager for a generation"""
        client = Observability.get_client()
        if client:
            return client.start_as_current_observation(name=name, as_type="generation", **kwargs)
        # Mock object
        class MockGen:
             def update(self, *args, **kwargs): pass
             def end(self, *args, **kwargs): pass
             def __enter__(self): return self
             def __exit__(self, *args): pass
        return MockGen()


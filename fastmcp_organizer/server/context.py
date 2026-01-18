from fastmcp_organizer.config import Config
from fastmcp_organizer.core.db import SQLiteStorage
from fastmcp_organizer.core.scanner import CompositeScanner
from fastmcp_organizer.core.classifier import HeuristicClassifier, LLMClassifier
from fastmcp_organizer.core.safety import StrictSafetyPolicy
from fastmcp_organizer.server.service import OrganizerService

class Context:
    _service_instance = None

    @classmethod
    def get_service(cls) -> OrganizerService:
        if cls._service_instance is None:
            # Initialize Dependencies
            storage = SQLiteStorage(Config.DB_PATH)
            scanner = CompositeScanner()
            
            # Chain Classifiers
            heuristic = HeuristicClassifier()
            classifier = LLMClassifier(fallback_classifier=heuristic)
            
            safety = StrictSafetyPolicy(allow_symlinks=Config.ALLOW_SYMLINKS)
            
            # Inject
            cls._service_instance = OrganizerService(
                scanner=scanner,
                classifier=classifier,
                storage=storage,
                safety=safety
            )
        return cls._service_instance

from abc import ABC, abstractmethod
from typing import Optional, List, Any, Dict
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime

# Domain Models (DTOs)
class FileMetadata(BaseModel):
    path: str
    size_bytes: int
    mtime: float
    hash: str
    content_sample: Optional[bytes] = None

class ClassificationResult(BaseModel):
    category: str
    confidence_score: float
    requires_deep_scan: bool
    path: str
    reasoning: Optional[str] = None

class PlanItem(BaseModel):
    id: str
    plan_id: str
    src_path: str
    dest_path: str
    reasoning: str
    status: str  # PENDING, SKIPPED, DONE, ERROR
    error_msg: Optional[str] = None

class ExecutionPlan(BaseModel):
    id: str
    root_dir: str
    status: str # CREATED, APPROVED, EXECUTED, FAILED
    created_at: datetime
    items: List[PlanItem]

# Interfaces
class IScanner(ABC):
    @abstractmethod
    def scan_file(self, path: Path) -> FileMetadata:
        """Calculates hash and basic metadata for a file."""
        pass

class IClassifier(ABC):
    @abstractmethod
    def classify(self, metadata: FileMetadata, content_sample: Optional[str] = None) -> ClassificationResult:
        """Determines the category and confidence for a file."""
        pass

class ISafetyPolicy(ABC):
    @abstractmethod
    def validate_path(self, root: Path, target: Path) -> bool:
        """Checks if a path is safe to access/move."""
        pass
    
    @abstractmethod
    def validate_move(self, src: Path, dest: Path) -> None:
        """Raises exception if move is unsafe."""
        pass

class IStorage(ABC):
    @abstractmethod
    def save_plan(self, plan: ExecutionPlan) -> None:
        """Persists a plan and its items."""
        pass

    @abstractmethod
    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Retrieves a plan by ID."""
        pass

    @abstractmethod
    def update_item_status(self, item_id: str, status: str, error_msg: Optional[str] = None) -> None:
        """Updates the status of a specific plan item."""
        pass
        
    @abstractmethod
    def get_cached_classification(self, file_hash: str) -> Optional[ClassificationResult]:
        """Retrieves cached classification if available."""
        pass

    @abstractmethod
    def cache_classification(self, file_hash: str, result: ClassificationResult) -> None:
        """Caches a classification result."""
        pass

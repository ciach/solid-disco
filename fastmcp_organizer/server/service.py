import uuid
import shutil
import logging
from typing import List, Optional
from datetime import datetime, timezone
from pathlib import Path

from fastmcp_organizer.core.interfaces import (
    IScanner, IClassifier, IStorage, ISafetyPolicy,
    ExecutionPlan, PlanItem, ClassificationResult
)
from fastmcp_organizer.utils.observability import Observability

class OrganizerService:
    def __init__(
        self,
        scanner: IScanner,
        classifier: IClassifier,
        storage: IStorage,
        safety: ISafetyPolicy
    ):
        self.scanner = scanner
        self.classifier = classifier
        self.storage = storage
        self.safety = safety

    def create_plan(self, root_dir: str) -> str:
        """
        Scans directory, classifies files, generates plan.
        Returns plan_id.
        """
        root_path = Path(root_dir)
        plan_id = str(uuid.uuid4())
        items: List[PlanItem] = []
        
        # Simple recursive scan
        # In production, might want to limit depth or safely walk
        for file_path in root_path.rglob("*"):
            if not file_path.is_file():
                continue
                
            # 1. Scan & Hash
            metadata = self.scanner.scan_file(file_path)
            
            # 2. Check Cache
            classification = self.storage.get_cached_classification(metadata.hash)
            if classification:
                print(f"[INFO] Using cached classification for: {file_path.name}")
                Observability.track_event("Cache Hit", {"path": str(file_path), "category": classification.category})
            
            # 3. Classify if needed
            if not classification:
                # Get content sample only if needed (already in metadata)
                content_sample = None
                if metadata.content_sample:
                     try:
                        content_sample = metadata.content_sample.decode('utf-8', errors='ignore')
                     except:
                        pass
                
                classification = self.classifier.classify(metadata, content_sample)
                self.storage.cache_classification(metadata.hash, classification)
            
            # 4. Determine Destination
            if classification.category == "Keep_Current_Location":
                continue # No move needed
                
            dest_dir = root_path / classification.category
            dest_path = dest_dir / file_path.name
            
            # Avoid collision logic (simple rename) - TODO: improve
            if dest_path == file_path:
                continue

            reasoning_text = classification.reasoning or f"Classified as {classification.category} (Confidence: {classification.confidence_score})"
            
            item = PlanItem(
                id=str(uuid.uuid4()),
                plan_id=plan_id,
                src_path=str(file_path),
                dest_path=str(dest_path),
                reasoning=reasoning_text,
                status="PENDING"
            )
            items.append(item)

        plan = ExecutionPlan(
            id=plan_id,
            root_dir=root_dir,
            status="CREATED",
            created_at=datetime.now(timezone.utc),
            items=items
        )
        
        self.storage.save_plan(plan)
        return plan_id

    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Retrieves a plan by ID."""
        return self.storage.get_plan(plan_id)

    def execute_plan(self, plan_id: str) -> List[str]:
        """
        Executes pending items in the plan safely.
        """
        plan = self.storage.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
            
        results = []
        
        for item in plan.items:
            if item.status == 'DONE':
                results.append(f"Skipped {item.src_path} (Already Done)")
                continue
            
            if item.status == 'SKIPPED':
                continue

            try:
                src = Path(item.src_path)
                dest = Path(item.dest_path)
                
                # Check existencve
                if not src.exists():
                     self.storage.update_item_status(item.id, 'ERROR', "Source not found")
                     continue

                # Safety Check
                self.safety.validate_move(src, dest)
                
                # Create parent dirs
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                # Move
                shutil.move(str(src), str(dest))
                
                self.storage.update_item_status(item.id, 'DONE')
                results.append(f"Moved {src.name} to {dest.parent.name}")
                
            except Exception as e:
                self.storage.update_item_status(item.id, 'ERROR', str(e))
                results.append(f"Error moving {item.src_path}: {e}")
                
        return results

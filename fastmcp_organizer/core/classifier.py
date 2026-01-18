from typing import Optional
from pathlib import Path
from pydantic import BaseModel
from openai import OpenAI

from fastmcp_organizer.core.interfaces import IClassifier, FileMetadata, ClassificationResult
from fastmcp_organizer.config import Config
from fastmcp_organizer.utils.observability import Observability

class HeuristicClassifier(IClassifier):
    def classify(self, metadata: FileMetadata, content_sample: Optional[str] = None) -> ClassificationResult:
        file_path = Path(metadata.path)
        name = file_path.name.lower()
        
        category = "Misc"
        confidence = 0.5
        requires_deep_scan = False

        # 1. Extension Heuristics
        if name.endswith(('.pdf', '.docx')):
            requires_deep_scan = True
            
        if name.endswith(('.jpg', '.png', '.jpeg')):
            category = "Images"
            confidence = 0.9

        # 2. Content Heuristics (Tier 1)
        if content_sample:
            lower_content = content_sample.lower()
            if "invoice" in lower_content or "total" in lower_content:
                category = "Financial"
                confidence = 0.85
                requires_deep_scan = True # Verification needed maybe

        # 3. Refine Confidence
        final_confidence = self._calculate_final_confidence(name, category, confidence)
        
        return ClassificationResult(
            category=category,
            confidence_score=final_confidence,
            requires_deep_scan=requires_deep_scan,
            path=metadata.path
        )

    def _calculate_final_confidence(self, file_name: str, category: str, base_score: float) -> float:
        score = base_score
        
        # Penalty: Generic categories
        if category in ["Misc", "Other"]:
            score -= 0.2
            
        # Boost: Filename corroboration
        if category.lower() in file_name.lower():
            score += 0.2
            
        return min(max(score, 0.0), 1.0)


class LLMClassifier(IClassifier):
    def __init__(self, fallback_classifier: IClassifier):
        self.fallback = fallback_classifier
        self.client = None
        if Config.OPENAI_API_KEY:
            self.client = OpenAI(api_key=Config.OPENAI_API_KEY)

    def classify(self, metadata: FileMetadata, content_sample: Optional[str] = None) -> ClassificationResult:
        # 1. Run Heuristic First
        heuristic_result = self.fallback.classify(metadata, content_sample)
        
        # 2. Use LLM if available (Mandatory - No heuristic short-circuit)
        if not self.client:
            return heuristic_result
            
        try:
            print(f"[INFO] calling LLM for: {metadata.path}")
            return self._call_llm(metadata, content_sample, heuristic_result)
        except Exception as e:
            Observability.track_event("LLM_Error", {"error": str(e)})
            return heuristic_result

    def _call_llm(self, metadata: FileMetadata, content_sample: Optional[str], heuristic_res: ClassificationResult) -> ClassificationResult:
        prompt = f"""
        Analyze this file to categorize it for a file organizer.
        Filename: {Path(metadata.path).name}
        Content Sample (first/last 4KB):
        {content_sample or "N/A"}
        
        Current Heuristic Category: {heuristic_res.category}
        
        Return a JSON object with:
        - category: A single word folder name (e.g. Financial, Personal, Work, Images, Code)
        - confidence_score: Float between 0.0 and 1.0
        - requires_deep_scan: Boolean
        """
        
        input_data = {"messages": [{"role": "user", "content": prompt}]}
        
        with Observability.generation(
            name="OpenAI Classification",
            model=Config.MODEL_NAME,
            input=input_data
        ) as gen:
            response = self.client.chat.completions.create(
                model=Config.MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful file organization assistant. Respond only in JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            import json
            content = response.choices[0].message.content
            gen.update(output=content)
            data = json.loads(content)
        
        return ClassificationResult(
            category=data.get("category", "Misc"),
            confidence_score=data.get("confidence_score", 0.5),
            requires_deep_scan=data.get("requires_deep_scan", False),
            path=metadata.path
        )

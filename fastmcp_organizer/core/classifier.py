import xml.etree.ElementTree as ET
import os
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
        
        if Config.LLM_PROVIDER == "ollama":
            self.client = OpenAI(
                base_url=Config.OLLAMA_BASE_URL,
                api_key="ollama" # Dummy key
            )
        elif Config.OPENAI_API_KEY:
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

        
        filename = Path(metadata.path).name
        sample = content_sample or "N/A"
        
        # 1. Load POML (File-based)
        poml_path = Path(__file__).parent.parent / "prompts" / "classifier.poml"
        poml_system = "You are a helpful assistant."
        poml_user = "Analyze {{filename}}"
        poml_schema = None
        
        try:
            if poml_path.exists():
                tree = ET.parse(poml_path)
                root = tree.getroot()
                poml_system = root.find("system-msg").text.strip()
                poml_user = root.find("human-msg").text.strip()
                schema_text = root.find("output-schema").text.strip()
                if schema_text:
                    import json
                    poml_schema = json.loads(schema_text)
        except Exception as e:
            print(f"[WARN] Failed to load POML: {e}")

        # 2. Determine Source (Langfuse > POML)
        langfuse = Observability.get_client()
        lf_prompt = None
        current_source = "poml"
        
        if langfuse:
            try:
                lf_prompt = langfuse.get_prompt("file_classifier")
                current_source = "langfuse"
            except:
                pass # Stick to POML

        # 3. Construct Messages
        messages = []
        if current_source == "langfuse" and lf_prompt:
             try:
                compiled = lf_prompt.compile(filename=filename, sample=sample, heuristic_category=heuristic_res.category)
                if isinstance(compiled, str):
                    messages = [{"role": "system", "content": "You are a file classification AI. Output strictly valid JSON."}, {"role": "user", "content": compiled}]
                elif isinstance(compiled, list):
                    messages = compiled
             except Exception as e:
                print(f"[WARN] Prompt compile error: {e}")
                current_source = "poml_fallback" # Logic fallback
        
        if not messages: # POML or Fallback
            # Inject schema into system prompt if available (Crucial for Ollama/Models without native struct output)
            schema_str = ""
            if poml_schema:
                import json
                schema_str = f"\n\nJSON Schema:\n{json.dumps(poml_schema, indent=2)}"
            
            user_msg = poml_user.replace("{{filename}}", filename)\
                                .replace("{{sample}}", sample)\
                                .replace("{{heuristic_category}}", heuristic_res.category)
            messages = [
                {"role": "system", "content": poml_system + schema_str},
                {"role": "user", "content": user_msg}
            ]

        # 4. Prepare Response Format
        # If POML has strict schema, we can use it. 
        # OpenAI/Ollama support varies. We'll use json_object for safest compat, 
        # or try json_schema if configured.
        # For this implementation, sticking to json_object plus schema instructions in prompt is safest cross-provider,
        # BUT user requested schema usage.
        
        resp_fmt = {"type": "json_object"}
        if poml_schema and Config.LLM_PROVIDER == "openai":
             # Strict Structured Output for OpenAI (requires method adjustment usually, passing response_format=schema)
             # But standard library expects {"type": "json_schema", "json_schema": ...}
             resp_fmt = {
                 "type": "json_schema",
                 "json_schema": poml_schema
             }

        with Observability.generation(
            name="OpenAI Classification",
            model=Config.MODEL_NAME,
            input=messages,
            prompt=lf_prompt, # None if POML
            metadata={"prompt_source": current_source}
        ) as gen:
            response = self.client.chat.completions.create(
                model=Config.MODEL_NAME,
                messages=messages,
                response_format=resp_fmt
            )
            
            import json
            content = response.choices[0].message.content
            gen.update(output=content)
            data = json.loads(content)
        
        return ClassificationResult(
            category=data.get("category", "Misc"),
            confidence_score=data.get("confidence_score", 0.5),
            requires_deep_scan=data.get("requires_deep_scan", False),
            path=metadata.path,
            reasoning=data.get("reasoning_summary")
        )

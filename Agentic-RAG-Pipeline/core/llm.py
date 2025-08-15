import os
import json
import re
import time
from typing import Optional, Dict, Any

import google.generativeai as genai

# Configure Gemini with your key
if os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Model names can evolve; these are stable aliases as of 2025
GEMINI_PRO = "gemini-1.5-pro"
GEMINI_FLASH = "gemini-1.5-flash"
EMB_MODEL = "models/text-embedding-004"   # embedding endpoint

def get_model(name=GEMINI_PRO, temperature=0.2, top_p=0.95, top_k=40, max_output_tokens=2048):
    return genai.GenerativeModel(
        model_name=name,
        generation_config={
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_output_tokens": max_output_tokens
        }
    )

def call_gemini(system_prompt: str, user_prompt: str, model_name: str = GEMINI_PRO,
                temperature: float = 0.2, max_output_tokens: int = 1024) -> str:
    """
    Synchronous call to Gemini with a system + user prompt.
    """
    model = get_model(name=model_name, temperature=temperature, max_output_tokens=max_output_tokens)
    # Concatenate system & user to maintain deterministic control
    full_prompt = f"{system_prompt.strip()}\n\nUSER:\n{user_prompt.strip()}"
    for attempt in range(3):
        try:
            resp = model.generate_content(full_prompt)
            # google-generativeai sometimes returns .text or candidates
            if hasattr(resp, "text") and resp.text:
                return resp.text
            # fallback parsing
            if getattr(resp, "candidates", None):
                parts = []
                for c in resp.candidates:
                    if getattr(c, "content", None) and getattr(c.content, "parts", None):
                        for p in c.content.parts:
                            parts.append(getattr(p, "text", "") or "")
                if parts:
                    return "\n".join(parts).strip()
            return ""
        except Exception as e:
            # simple backoff
            time.sleep(0.7 * (attempt + 1))
            if attempt == 2:
                raise e
    return ""

def embed_text(text: str, task_type: str = "retrieval_document") -> list:
    """
    Returns a 768-d vector via text-embedding-004.
    task_type: 'retrieval_document' or 'retrieval_query'
    """
    # New SDK returns {'embedding': {'values': [...]}}
    r = genai.embed_content(model=EMB_MODEL, content=text, task_type=task_type)
    if isinstance(r, dict):
        emb = r.get("embedding", {})
        values = emb.get("values") if isinstance(emb, dict) else None
        if values:
            return values
        # Older form fallback
        if "embedding" in r and isinstance(r["embedding"], list):
            return r["embedding"]
    # last resort: empty vector
    return [0.0] * 768

def safe_json_loads(txt: str) -> Optional[Dict[str, Any]]:
    """
    Extracts and parses the first JSON object from txt.
    """
    if not txt:
        return None
    # Try direct
    try:
        return json.loads(txt)
    except Exception:
        pass

    # Find first {...} block
    start = txt.find("{")
    end = txt.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = txt[start:end+1]
        try:
            return json.loads(candidate)
        except Exception:
            # Fix common JSON issues (single quotes, trailing commas)
            cleaned = re.sub(r"(\s)([A-Za-z0-9_]+)\s*:", r'\1"\2":', candidate)  # quote keys
            cleaned = cleaned.replace("'", '"')
            cleaned = re.sub(r",\s*}", "}", cleaned)
            cleaned = re.sub(r",\s*]", "]", cleaned)
            try:
                return json.loads(cleaned)
            except Exception:
                return None
    return None

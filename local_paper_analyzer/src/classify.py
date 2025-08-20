import json, re
from typing import Dict, List, Tuple
from .llm_client import LLMClient

LABELS = ["Agent", "LLM", "Memory", "RAG", "Spatial Learning"]

CLASSIFY_PROMPT = (
    "You are a domain expert classifying arXiv papers for a daily research digest.\n"
    "Given the TITLE and ABSTRACT (and optional excerpt), assign **relevance scores** in [0,1] to these labels:\n"
    f"{', '.join(LABELS)}.\n"
    "Interpretation:\n"
    "- Agent: autonomous agents / tool-using / multi-agent / planning / agent frameworks.\n"
    "- LLM: foundation models, pretraining, instruction-tuning, inference/training techniques for large language models.\n"
    "- Memory: episodic/long-term memory, retrieval memory modules, knowledge editing, memory-augmented architectures.\n"
    "- RAG: retrieval-augmented generation, indexing, retrievers, hybrid search, grounding with external corpora.\n"
    "- Spatial Learning: 3D/embodied/spatial reasoning, navigation, mapping, spatial grounding.\n"
    "Return STRICT JSON with keys exactly: {{\"scores\": {{label: float}}, \"primary\": \"<one of labels>\"}}.\n"
    "No extra text.\n\n"
    "TITLE: {title}\n"
    "ABSTRACT: {abstract}\n"
    "{extra}\n"
)

def _extract_json(s: str) -> dict:
    m = re.search(r'\{.*\}', s, re.DOTALL)
    if not m: return {}
    try: return json.loads(m.group(0))
    except Exception:
        s2 = re.sub(r',\s*}', '}', m.group(0)); s2 = re.sub(r',\s*]', ']', s2)
        try: return json.loads(s2)
        except Exception: return {}

def classify_one(llm: LLMClient, title: str, abstract: str, excerpt: str = "", labels: List[str] = None) -> Tuple[Dict[str, float], str]:
    if labels is None: labels = LABELS
    msg = [{"role":"user","content": CLASSIFY_PROMPT.format(title=title.strip(), abstract=abstract.strip(), extra=(f"EXCERPT: {excerpt[:2000]}" if excerpt else "EXCERPT: (none)"))}]
    resp = llm.chat(msg, temperature=0.0, max_tokens=400)
    data = _extract_json(resp) or {}
    scores = {k: float(v) for k, v in (data.get("scores") or {}).items() if k in labels}
    for L in labels: scores.setdefault(L, 0.0)
    primary = data.get("primary")
    if primary not in labels: primary = max(scores.items(), key=lambda kv: kv[1])[0] if scores else labels[0]
    return scores, primary

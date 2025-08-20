from typing import List, Dict, Tuple
from .llm_client import LLMClient
from .utils import extract_json_block
from .formatting import clean_markdown

TLDR_PROMPT = (
    "Write a crisp **TL;DR** for the paper below in 2 sentences, technical but compact.\n"
    "Return plain text only.\n\n"
    "TITLE: {title}\nABSTRACT: {abstract}\n"
)

MAP_PROMPT = (
    "You are extracting key facts from a research paper PAGE to aid faithful summarization.\n"
    "Given PAGE_NUM and PAGE_TEXT, output bullet points. Each bullet MUST cite the page like [p.{page_num}].\n"
    "Focus on: problem, method modules, datasets, metrics, key numbers, limitations. Keep bullets short.\n"
    "PAGE_NUM: {page_num}\n"
    "PAGE_TEXT (truncated):\n---\n{page_text}\n---"
)

REDUCE_PROMPT = (
    "You are writing a faithful paper digest using page-anchored bullets.\n"
    "Using TITLE, ABSTRACT, and BULLETS (each with [p.X] markers), produce:\n"
    "1) **Method Card** with fields: Task/Domain, Core Idea (1 sentence), Components/Architecture, Training/Inference Setup (params, context len, tricks), Datasets, Results (numbers with [p.X]), Limitations (with [p.X]), Links (if present).\n"
    "2) **Full Summary**: 1 short paragraph, include key numbers with [p.X].\n"
    "3) **Discussion Prompts**: 3 thoughtful questions for a research group.\n"
    "Return in Markdown with clear headings. Preserve [p.X] citations.\n\n"
    "TITLE: {title}\nABSTRACT: {abstract}\nBULLETS:\n{bullets}"
)

REPRO_PROMPT = (
    "Assess REPRODUCIBILITY SIGNALS from TITLE/ABSTRACT and PAGE BULLETS (with [p.X]).\n"
    "Return STRICT JSON with keys:\n"
    "{{"
    "\"code\": {{ \"present\": bool, \"note\": str }}, "
    "\"weights\": {{ \"present\": bool, \"note\": str }}, "
    "\"data\": {{ \"present\": bool, \"note\": str }}, "
    "\"train_details\": {{ \"present\": bool, \"note\": str }}, "
    "\"eval_scripts\": {{ \"present\": bool, \"note\": str }}, "
    "\"inference_params\": {{ \"present\": bool, \"note\": str }}"
    "}}\n"
    "Use [p.X] page refs where relevant. If uncertain, set present=false and explain.\n\n"
    "TITLE: {title}\nABSTRACT: {abstract}\nBULLETS:\n{bullets}"
)

SOTA_PROMPT = (
    "From the paper info below, extract a list of SOTA-style results as JSON array.\n"
    "Each item with keys: metric, dataset, value (number), baseline (optional), delta (optional), page (int).\n"
    "Only include items where a concrete number is mentioned. If none, return [].\n\n"
    "TITLE: {title}\nABSTRACT: {abstract}\nBULLETS:\n{bullets}"
)

BILINGUAL_PROMPT = (
    "Translate the following Markdown from {src} to {tgt}. Keep code, links, [p.X] citations intact.\n"
    "Return only the translated Markdown.\n\n"
    "{content}"
)

def two_stage_summary(llm: LLMClient, title: str, abstract: str) -> str:
    tldr = llm.chat([{"role":"user","content": TLDR_PROMPT.format(title=title, abstract=abstract)}],
                    temperature=0.1, max_tokens=200)
    return tldr.strip()

def map_pages(llm: LLMClient, pages: List[Tuple[int, str]]) -> List[str]:
    bullets = []
    for page_num, text in pages:
        snippet = text[:3500]
        content = MAP_PROMPT.format(page_num=page_num, page_text=snippet)
        res = llm.chat([{"role":"user","content":content}], temperature=0.1, max_tokens=900)
        bullets.append(res.strip())
    return bullets

def reduce_with_cards(llm: LLMClient, title: str, abstract: str, bullets_joined: str) -> str:
    content = REDUCE_PROMPT.format(title=title, abstract=abstract, bullets=bullets_joined)
    md = llm.chat([{"role":"user","content":content}], temperature=0.2, max_tokens=1200)
    return md.strip()

def repro_check(llm: LLMClient, title: str, abstract: str, bullets_joined: str) -> dict:
    content = REPRO_PROMPT.format(title=title, abstract=abstract, bullets=bullets_joined)
    res = llm.chat([{"role":"user","content":content}], temperature=0.0, max_tokens=500)
    return extract_json_block(res) or {}

def extract_sota(llm: LLMClient, title: str, abstract: str, bullets_joined: str) -> list:
    content = SOTA_PROMPT.format(title=title, abstract=abstract, bullets=bullets_joined)
    res = llm.chat([{"role":"user","content":content}], temperature=0.0, max_tokens=700)
    data = extract_json_block(res)
    if isinstance(data, list): return data
    return []

def translate_md(llm: LLMClient, md: str, src_lang: str, tgt_lang: str) -> str:
    res = llm.chat([{"role":"user","content": BILINGUAL_PROMPT.format(src=src_lang, tgt=tgt_lang, content=md)}],
                   temperature=0.0, max_tokens=1400)
    return res.strip()

def format_sota_table(items: list) -> str:
    if not items: return "_No explicit SOTA-style numbers extracted._"
    headers = ["Metric","Dataset","Value","Baseline","Delta","Page"]
    lines = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"]*len(headers)) + "|"]
    for x in items:
        metric = str(x.get("metric","")); dataset = str(x.get("dataset",""))
        value = str(x.get("value","")); baseline = str(x.get("baseline",""))
        delta = str(x.get("delta","")); page = str(x.get("page",""))
        lines.append("|" + "|".join([metric,dataset,value,baseline,delta,page]) + "|")
    return "\n".join(lines)

def format_repro_checklist(d: dict) -> str:
    if not d: return "_Reproducibility signals: unknown._"
    def box(b): return "✅" if b else "❌"
    lines = []
    for key in ["code","weights","data","train_details","eval_scripts","inference_params"]:
        item = d.get(key,{})
        lines.append(f"- {key}: {box(item.get('present', False))} — {item.get('note','')}")
    return "\n".join(lines)

def analyze_paper(llm: LLMClient, title: str, abstract: str, pages: List[Tuple[int,str]],
                  generate_sota=True, generate_repro=True, bilingual=None) -> dict:
    tldr = two_stage_summary(llm, title, abstract)
    page_bullets = map_pages(llm, pages)
    bullets_joined = "\n\n".join(f"- From page {pno}:\n{b}" for (pno, _), b in zip(pages, page_bullets))
    digest_md = reduce_with_cards(llm, title, abstract, bullets_joined)

    repro_json = extract_sota_list = []
    repro_json = {}
    if generate_repro:
        repro_json = repro_check(llm, title, abstract, bullets_joined)
    if generate_sota:
        extract_sota_list = extract_sota(llm, title, abstract, bullets_joined)

    english_md_parts = [
        f"**TL;DR:** {tldr}",
        "## Method Card",
        digest_md,
        "## SOTA Table",
        format_sota_table(extract_sota_list),
        "## Reproducibility Checklist",
        format_repro_checklist(repro_json)
    ]
    english_md = clean_markdown("\n\n".join(english_md_parts))

    out = {
        "tldr": tldr,
        "digest_md": digest_md,
        "sota": extract_sota_list,
        "repro": repro_json,
        "english_md": english_md
    }

    if bilingual and bilingual.get("enabled"):
        primary = bilingual.get("primary","en")
        secondary = bilingual.get("secondary","zh")
        src_lang = "English" if primary=="en" else "Chinese"
        tgt_lang = "Chinese" if secondary=="zh" else "English"
        translated = translate_md(llm, english_md, src_lang, tgt_lang)
        out["bilingual_md"] = clean_markdown(translated)

    return out

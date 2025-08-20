import os
import arxiv
import argparse
import datetime
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from .utils import utc_minute_str, load_state, save_state, ensure_dir, update_progress
from .llm_client import LLMClient
from .summarize import analyze_paper
from .emailer import send_email
from .docx_export import markdown_to_docx
from .formatting import markdown_to_html

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def download_pdf(paper: arxiv.Result, dest_dir: str) -> str:
    pdf_path = os.path.join(dest_dir, f"{paper.get_short_id()}.pdf")
    paper.download_pdf(filename=pdf_path, dirpath=None)
    return pdf_path

def extract_pdf_pages(pdf_path: str, max_pages: int = 12) -> list:
    try:
        import fitz
        doc = fitz.open(pdf_path)
        pages = []
        n = min(len(doc), max_pages)
        for i in range(n):
            page = doc.load_page(i)
            pages.append((i+1, page.get_text("text")))
        return pages
    except Exception:
        return []

def read_config(path: str) -> dict:
    import yaml
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def to_utc_range(recency_days: int) -> tuple[str, str]:
    now_local = datetime.datetime.now().astimezone()
    start_local = now_local - datetime.timedelta(days=recency_days)
    return utc_minute_str(start_local), utc_minute_str(now_local)

def build_query(categories, start_utc_min, end_utc_min) -> str:
    cats = ' OR '.join(f'cat:{c}' for c in categories)
    date_clause = f'submittedDate:[{start_utc_min} TO {end_utc_min}]'
    return f'({cats}) AND {date_clause}'

def md_escape(s: str) -> str:
    return s.replace('|','\|')

def htmlify(md: str) -> str:
    # Deprecated in favor of markdown_to_html; keep for compatibility
    return md.replace('\n', '<br>')

def sanitize_ascii_label(name: str) -> str:
    import re
    s = name.strip().replace(' ', '_').lower()
    s = re.sub(r'[^a-z0-9_]', '', s)
    return s or 'label'

def md_table(rows, headers):
    out = ["|" + "|".join(headers) + "|", "|" + "|".join(["---"]*len(headers)) + "|"]
    out += ["|" + "|".join(r) + "|" for r in rows]
    return "\n".join(out)

def run(cfg_path: str):
    load_dotenv()
    cfg = read_config(cfg_path)

    run_cfg = cfg.get('run', {})
    llm_cfg = cfg.get('llm', {})
    email_cfg = cfg.get('email', {})
    classify_cfg = cfg.get('classification', {})
    summ_cfg = cfg.get('summarization', {})
    bilingual_cfg = cfg.get('bilingual', {})

    recency_days   = int(run_cfg.get('recency_days', 6))
    max_papers     = int(run_cfg.get('max_papers', 600))
    categories     = run_cfg.get('categories', ['cs.AI','cs.LG','cs.CL'])
    out_dir        = run_cfg.get('output_dir', 'papers')
    out_md         = run_cfg.get('output_markdown', 'report.md')
    out_docx       = run_cfg.get('output_docx', 'report.docx')
    progress_json  = run_cfg.get('progress_file', 'run_status.json')
    dedupe_db      = run_cfg.get('dedupe_db', 'state.json')

    labels         = classify_cfg.get('labels', ['Agent','LLM','Memory','RAG','Spatial Learning'])
    topk           = int(classify_cfg.get('top_k_per_label', 10))
    use_full_text  = bool(classify_cfg.get('use_full_text', False))

    ensure_dir(out_dir)

    start_utc, end_utc = to_utc_range(recency_days)
    query = build_query(categories, start_utc, end_utc)

    client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=3)
    search = arxiv.Search(query=query, max_results=max_papers, sort_by=arxiv.SortCriterion.SubmittedDate, sort_order=arxiv.SortOrder.Descending)

    update_progress(progress_json, 'fetching', 0, 0, 'querying arXiv')
    results = list(client.results(search))
    update_progress(progress_json, 'fetched', len(results), len(results), 'papers fetched')

    llm = LLMClient(provider=llm_cfg.get('provider','ollama'), endpoint=llm_cfg.get('endpoint','http://localhost:11434'), model=llm_cfg.get('model','qwen2.5-coder:14b'))

    from .classify import classify_one

    buckets = {L: [] for L in labels}

    for i, paper in enumerate(tqdm(results, desc="Classifying"), start=1):
        update_progress(progress_json, 'classifying', i, len(results), paper.get_short_id())
        title = paper.title.strip()
        abstract = paper.summary.strip()
        excerpt = ""

        if use_full_text:
            try:
                pdf_path = download_pdf(paper, out_dir)
                excerpt = extract_pdf_pages(pdf_path, max_pages=summ_cfg.get('max_pages', 12))
            except Exception:
                excerpt = ""

        scores, primary = classify_one(llm, title, abstract, excerpt, labels=labels)
        for L in labels:
            buckets[L].append((scores.get(L, 0.0), paper, scores))

    selected = {L: sorted(buckets[L], key=lambda x: x[0], reverse=True)[:topk] for L in labels}

    total_to_summarize = sum(len(v) for v in selected.values())
    done_sum = 0
    update_progress(progress_json, 'summarizing', 0, total_to_summarize, 'starting summaries')

    lines = []
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    lines.append(f"# Daily arXiv Digest ({today})\n")
    lines.append(f"**Window (UTC):** {start_utc} → {end_utc} | **Categories:** {', '.join(categories)} | **Model:** {llm_cfg.get('model','qwen2.5-coder:14b')}\n")    

    for L in labels:
        rows = []
        lines.append(f"## {L} — Top {topk}\n")
        headers = ["#", "Title", "arXiv", "Date", "PrimaryCat", "Score"]
        for idx, (score, paper, scores) in enumerate(selected[L], start=1):
            pid = paper.get_short_id()
            title = md_escape(paper.title.strip())
            link = f"[{pid}]({paper.entry_id})"
            date = str(paper.published.date())
            pcat = paper.primary_category
            rows.append([str(idx), title, link, date, pcat, f"{score:.2f}"])
        lines.append(md_table(rows, headers) + "\n")

        for idx, (score, paper, scores) in enumerate(selected[L], start=1):
            title = paper.title.strip()
            abstract = paper.summary.strip()
            full_pages = []
            try:
                pdf_path = download_pdf(paper, out_dir)
                full_pages = extract_pdf_pages(pdf_path, max_pages=summ_cfg.get('max_pages', 12))
            except Exception:
                full_pages = []
            analysis = analyze_paper(llm, title=title, abstract=abstract, pages=full_pages, generate_sota=summ_cfg.get('generate_sota', True), generate_repro=summ_cfg.get('generate_repro', True), bilingual=bilingual_cfg)
            lines.append(f"### {L} · {idx}. {md_escape(title)}\n")
            lines.append(f"**arXiv**: [{paper.get_short_id()}]({paper.entry_id}) | **PDF**: {paper.pdf_url} | **Score**: {score:.2f}\n")
            lines.append(analysis['english_md'] + "\n")
            if analysis.get('bilingual_md'):
                lines.append("## （中文）Bilingual Translation\n")
                lines.append(analysis['bilingual_md'] + "\n")
            done_sum += 1
            update_progress(progress_json, 'summarizing', done_sum, total_to_summarize, paper.get_short_id())
        lines.append("\n---\n")

    md_path = out_md
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    # DOCX
    try:
        markdown_to_docx("\n".join(lines), out_docx)
    except Exception as e:
        print(f"[WARN] DOCX export failed: {e}")

    # Email
    if cfg.get('email', {}).get('enabled', False):
        update_progress(progress_json, 'email', 0, 1, 'sending email')
        md_text = "\n".join(lines)
        body_html = markdown_to_html(md_text)
        try:
            send_email(host=cfg['email']['smtp_server'], port=int(cfg['email']['smtp_port']), username=cfg['email']['username'], password=cfg['email']['password'], from_addr=cfg['email']['from_addr'], to_addrs=cfg['email']['to_addrs'], subject=f"Daily arXiv Digest ({today})", html_body=body_html, attachments=[out_md, out_docx])
            print("Email sent.")
            update_progress(progress_json, 'email', 1, 1, 'email sent')
        except Exception as e:
            print("Email failed:", e)

    print(f"Wrote report to {md_path}. CSVs in {out_dir}.")
    update_progress(progress_json, 'done', None, None, 'completed')

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config.yaml', help='Path to config.yaml')
    args = ap.parse_args()
    run(args.config)

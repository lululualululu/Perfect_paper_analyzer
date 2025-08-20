import re
from typing import List

def clean_markdown(md: str) -> str:
    s = md
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"^(#{1,6})\s*[-*]+\s*", r"\1 ", s, flags=re.MULTILINE)
    s = re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*[•·‣◦]\s*", "- ", s, flags=re.MULTILINE)
    s = re.sub(r"\[p\.\s*(?:X|x|N/?A|NA)\]", "", s)
    s = re.sub(r"\[p\.\s*(\d+)\]", r"[p.\1]", s)

    lines = s.split("\n")
    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" in line and not re.fullmatch(r"\s*\|?\s*-{3,}.*", line):
            block = [line]
            j = i + 1
            while j < len(lines) and "|" in lines[j]:
                block.append(lines[j]); j += 1
            cols = [c.strip() for c in block[0].split("|") if c.strip() != ""]
            sep = "|" + "|".join(["---"] * len(cols)) + "|"
            if len(block) == 1 or not re.fullmatch(r"\s*\|?.*-{3,}.*\|?.*", block[1]):
                block.insert(1, sep)
            if out and out[-1].strip() != "":
                out.append("")
            out.extend(block)
            if j < len(lines) and lines[j].strip() != "":
                out.append("")
            i = j
            continue
        out.append(line); i += 1
    s = "\n".join(out)
    s = re.sub(r"([^\n])\n(#{1,6}\s)", r"\1\n\n\2", s)
    s = re.sub(r"[ \t]+$", "", s, flags=re.MULTILINE)
    return s

def markdown_to_html(md: str) -> str:
    from markdown import markdown as md_render
    html = md_render(md, extensions=["extra", "sane_lists", "toc", "nl2br"])
    return html

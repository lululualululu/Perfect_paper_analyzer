# Local arXiv Daily Analyzer

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)
![LLM: Ollama](https://img.shields.io/badge/LLM-Ollama-black)
![arXiv](https://img.shields.io/badge/Data-arXiv-red)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

> 📨 每日自动抓取 **cs.AI / cs.LG / cs.CL（可更改）**，用本地/api 大模型（默认：`qwen2.5-coder:14b` via Ollama）进行**分类+摘要**，并生成 **Markdown + DOCX** 日报，邮件发送（附带报告），同时输出 **进度 JSON** 便于实时查看。

---

## ✨ Features

* 🔎 **检索窗口**：默认近 `6` 天，按天抓取；可配每日最多 `n` 篇（总上限 `max_papers`）。
* 🧠 **本地/Api LLM**：Ollama / 自定义端点；默认 `qwen2.5-coder:14b`。
* 🏷️ **自定义二级类别自动分类**：Agent / LLM / Memory / RAG （每类 Top-K，可添加自己领域类别，自定义Top-K范围）。
* 📝 **两阶段摘要**：TL;DR → 完整 Digest（**Method Card** + 讨论问题）。
* ✅ **复现清单**：代码/权重/数据/训练细节/评测脚本/推理超参。
* 🏆 **SOTA 表**：自动抽取 metric/dataset/value/baseline/delta/page。
* 🌐 **双语输出**（可开关）：保留链接。
* 📦 **导出**：`report.md` + `report.docx`（邮件正文使用 **真·Markdown→HTML** 渲染）。
* 📊 **进度追踪**：`run_status.json` 实时写入当前阶段与进度。
* 📧 **邮件发送**：支持 QQ 邮箱（465/SSL）等，**附上 MD & DOCX**。

---

## 🗂️ Project Structure

```
perfect_paper_analyzer/
├─ config.yaml
├─ requirements.txt
├─ report.md                 # 输出：Markdown 日报
├─ report.docx               # 输出：Word 日报
├─ run_status.json           # 输出：实时进度
├─ papers/                   # 下载的PDF & 每类CSV
└─ src/
   ├─ main.py
   ├─ llm_client.py
   ├─ classify.py
   ├─ summarize.py
   ├─ formatting.py          # Markdown 清洗 & markdown_to_html
   ├─ docx_export.py         # Markdown → DOCX（标题/列表/代码/表格）
   ├─ emailer.py             # 支持附件 & 465/587
   └─ utils.py               # 进度JSON、工具函数
```

---

## 🚀 Quick Start

### 1) Environment

```bash
# Python 3.9+
conda create -n paper python=3.9
conda activate paper
cd local_paper_analyzer\
pip install -r requirements.txt
```

### 2) Local LLM (Ollama)

```bash
# 安装 Ollama 后：
ollama pull qwen2.5-coder:14b
# 查看/停止
ollama ps
ollama stop qwen2.5-coder:14b
```

### 3) Configure

复制并编辑：

```bash
cp config.example.yaml config.yaml
```

关键项（节选）：

```yaml
run:
  recency_days: 6
  max_papers: 200
  categories: [cs.AI, cs.LG, cs.CL]
  output_dir: papers
  output_markdown: report.md
  output_docx: report.docx
  progress_file: run_status.json

llm:
  provider: ollama
  endpoint: http://localhost:11434
  model: qwen2.5-coder:14b

classification:
  labels: [Agent, LLM, Memory, RAG]
  top_k_per_label: 10
  use_full_text: true       

summarization:
  max_pages: 12             # 每篇PDF最多抽取的页
  generate_sota: true
  generate_repro: true
  team_prompts: true

bilingual:
  enabled: false            # 设为 true 开启双语
  primary: en
  secondary: zh

email:
  enabled: true
  smtp_server: smtp.qq.com
  smtp_port: 465            # QQ 推荐 465/SSL
  username: "YOUR_QQ@qq.com"
  password: "APP_PASSWORD"  # QQ 授权码
  from_addr: "YOUR_QQ@qq.com"
  to_addrs: ["YOUR_QQ@qq.com"]
```

> 🔐 别把邮箱授权码提交到仓库。可用环境变量或 CI Secrets。

### 4) Run

```bash
# 推荐包运行（已解决相对导入问题）
python -m src.main --config config.yaml
```

---


## 🛠️ Commands

### Real-time progress

```bash
watch -n 1 cat run_status.json
# {"stage": "summarizing", "current": 7, "total": 50, "note": "2508.01234", "ts": "..."}
```

### Schedule (daily 08:00)

**Linux/macOS (crontab)**

```bash
0 8 * * * /usr/bin/env bash -lc 'cd /ABS/PATH/local_paper_analyzer && source .venv/bin/activate && python -m src.main --config config.yaml >> run.log 2>&1'
```

**Windows (Task Scheduler)**

* Program: `python`
* Arguments: `-m src.main --config config.yaml`
* Start in: `C:\ABS\PATH\local_paper_analyzer`

---

## ⚙️ Tuning Tips

* ⏱️ **更快**：

  * `summarization.max_pages: 6~8`
  * `classification.top_k_per_label: 5`（调试期）
  * `bilingual.enabled: false`
* 🎯 **更准**：

  * `use_full_text: true`
  * 保持 `generate_repro: true`、`generate_sota: true`
* 📬 **邮件稳定**：QQ 用 `smtp_port: 465`，SSL 直连更稳。

---

## 📤 Outputs

* `report.md`：每日 Markdown 报告
* `report.docx`：可直接分发的 Word 报告（标题/列表/代码/表格）
* `papers/top_*.csv`：n类 Top-K 清单
* `run_status.json`：实时阶段与进度

---

## 🧪 Labels (n类)

| Label            | 说明                        |
| ---------------- | ------------------------- |
| Agent            | 自主代理、多智能体、工具使用、规划/执行      |
| LLM              | 预训练/指令/推理&训练技巧、基础模型       |
| Memory           | 记忆模块、写回/遗忘/压缩、知识编辑        |
| RAG              | 检索增强、Hybrid 搜索、重排序、长上下文裁剪 |


---

## 🔐 Privacy & Security

* 不要把 `config.yaml` 中的敏感字段提交到仓库。
* 优先使用环境变量/CI Secrets。
* 仅用于公开的 arXiv 数据与本地 PDF 解析，不上传文档至第三方服务（除非你自行配置）。

---

## 📈 Future

* 关键词预筛 + LLM 打分融合（更省时）
* 多样性约束（MMR / coverage）
* 周报自动汇总（趋势/增量/SOTA 曲线）
* 更丰富的 DOCX 样式（可点击超链接、代码高亮）
* 更有价值的数据内容
* UI界面
---

## 📝 License

MIT © 2025

---

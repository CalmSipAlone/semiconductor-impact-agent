"""Build the reading index and bibliography from verified paper metadata.

Uses the Python standard library only. Does not fetch papers or run models.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
papers = json.loads((ROOT / "papers.json").read_text(encoding="utf-8"))
assert len(papers) == 12
assert len({p["id"] for p in papers}) == len(papers)
for p in papers:
    assert p["venue"] in {"ACL", "ACL-IJCNLP", "EMNLP", "ICLR", "NeurIPS"}
    assert p["track"].startswith("Main conference")
    assert p["official_url"].startswith("https://")
    assert p["pdf_url"].startswith("https://")

intro = """# 顶尖会议论文与阅读指南

检索整理日期：2026-10-08。按团队要求，本次仅纳入ACL、EMNLP、ICLR、NeurIPS主会正式发表的研究论文，不纳入仅有arXiv预印本、Workshop、Demo或Findings记录的论文。共12篇。

这是一份基于正式论文集、作者页面、摘要及元数据的阅读筛选，不代表已经逐页精读或复现实验。各条的“项目用途”是结合本项目提出的实施建议，并非论文在半导体场景中已经验证的结果。

提供原始论文页面和公开全文PDF链接，点击即可阅读；没有将第三方PDF复制进公开Git仓库。ReAct的OpenReview页面本次访问遇到浏览器验证，已以作者代码仓库及ICLR camera-ready版本交叉确认，并保留说明。

## 建议优先阅读

1. **B，计算机成员**：StructGPT → TAT-QA → FinQA → ALCE；再看RAG和ReAct。
2. **D，AI成员**：ReAct → RAG → StructGPT → ALCE；后续看Think-on-Graph和Self-RAG。
3. **A，工商管理成员**：FinQA → TAT-QA → ALCE；重点理解计算过程、证据和评价。
4. **C/E，产业与材料成员**：Think-on-Graph和SciREX；重点协助定义可核验的关系与证据。

## 论文总表

| 论文 | 正式会议 | 对应模块 | 优先级 | 页面 | 公开全文 |
| --- | --- | --- | --- | --- | --- |
"""
rows = [
    f'| {p["short_name"]} | {p["venue"]} {p["year"]} | {p["category"]} | {p["priority"]} | [论文页面]({p["official_url"]}) | [PDF]({p["pdf_url"]}) |'
    for p in papers
]
sections = []
for i, p in enumerate(papers, 1):
    code = f'；[作者代码]({p["code_url"]})' if p["code_url"] else ""
    sections.append(
        f'## {i}. {p["short_name"]} — {p["venue"]} {p["year"]}\n\n'
        f'**标题：** {p["title"]}\n\n'
        f'**作者：** {", ".join(p["authors"])}\n\n'
        f'[论文页面]({p["official_url"]})；[公开全文PDF]({p["pdf_url"]}){code}\n\n'
        f'- **论文内容：** {p["method"]}\n'
        f'- **项目可借鉴之处：** {p["project_use"]}\n'
        f'- **适用边界：** {p["boundary"]}\n'
        f'- **建议阅读成员：** {"、".join(p["readers"])}\n'
        f'- **发表核验：** {p["verification_note"]} [核验来源]({p["verification_url"]})\n'
    )
footer = """## 如何用于计划书

技术方案可分别引用ReAct的工具编排、RAG的外部证据检索、StructGPT的结构化接口、FinQA/TAT-QA的数值计算及ALCE的引用评价。应说明采用的是哪些设计思路，哪些模块实际实现了，避免把“引用论文”写成“复现了完整方法”。

这些论文主要支撑AI和数据系统的技术设计。它们不提供具体企业的树脂成本占比、价格转嫁系数，也不证明政策对企业利润的因果影响。化学材料知识、企业参数及经济传导证据仍需另行核验。本次未将一般材料综述或经济期刊论文混入“顶尖会议”清单。

FinRobot、通用GraphRAG报告和Docling技术报告等虽然可能相关，但本次没有核实其符合上述主会正式发表标准，因此不纳入本清单；这不代表否认其技术价值。

## 引用与维护

- [BibTeX参考文献](references.bib)：可用于论文或LaTeX引用；题名、作者、年份和会议依据本清单，页码等细节请以正式论文集导出的引用为准。
- [结构化元数据](papers.json)：保存会议、原文、核验来源和项目用途。
- `python research/build_index.py`：从元数据重新生成本页和BibTeX，只使用标准库，不会联网或下载PDF。

正文表述和翻译为本项目整理；论文版权与代码许可证分别归原权利人或原项目。引用及复用代码时保留来源并检查相应许可证。
"""
(ROOT / "README.md").write_text(intro + "\n".join(rows) + "\n\n" + "\n".join(sections) + "\n" + footer, encoding="utf-8")

def bib_escape(text):
    return text.replace("&", r"\&").replace("%", r"\%")

entries = []
for p in papers:
    authors = " and ".join(p["authors"])
    entries.append(
        f'@inproceedings{{{p["id"]},\n'
        f'  title = {{{{{bib_escape(p["title"])}}}}},\n'
        f'  author = {{{authors}}},\n'
        f'  booktitle = {{{p["venue"]}}},\n'
        f'  year = {{{p["year"]}}},\n'
        f'  url = {{{p["official_url"]}}}\n'
        f'}}\n'
    )
(ROOT / "references.bib").write_text("\n".join(entries), encoding="utf-8")
print(f"Generated reading index and bibliography for {len(papers)} papers.")

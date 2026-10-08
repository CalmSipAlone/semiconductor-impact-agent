# 顶尖会议论文与阅读指南

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
| ReAct | ICLR 2023 | 智能体与工具 | 优先 | [论文页面](https://openreview.net/forum?id=WE_vluYUL-X) | [PDF](https://arxiv.org/pdf/2210.03629v3) |
| RAG | NeurIPS 2020 | 证据检索与核验 | 优先 | [论文页面](https://papers.nips.cc/paper_files/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html) | [PDF](https://proceedings.nips.cc/paper/2020/file/6b493230205f780e1bc26945df7481e5-Paper.pdf) |
| FinQA | EMNLP 2021 | 财报与数值计算 | 优先 | [论文页面](https://aclanthology.org/2021.emnlp-main.300/) | [PDF](https://aclanthology.org/2021.emnlp-main.300.pdf) |
| TAT-QA | ACL-IJCNLP 2021 | 财报与数值计算 | 优先 | [论文页面](https://aclanthology.org/2021.acl-long.254/) | [PDF](https://aclanthology.org/2021.acl-long.254.pdf) |
| StructGPT | EMNLP 2023 | 智能体与工具 | 优先 | [论文页面](https://aclanthology.org/2023.emnlp-main.574/) | [PDF](https://aclanthology.org/2023.emnlp-main.574.pdf) |
| ALCE | EMNLP 2023 | 证据检索与核验 | 优先 | [论文页面](https://aclanthology.org/2023.emnlp-main.398/) | [PDF](https://aclanthology.org/2023.emnlp-main.398.pdf) |
| ConvFinQA | EMNLP 2022 | 财报与数值计算 | 扩展 | [论文页面](https://aclanthology.org/2022.emnlp-main.421/) | [PDF](https://aclanthology.org/2022.emnlp-main.421.pdf) |
| Think-on-Graph | ICLR 2024 | 图谱与多跳关系 | 扩展 | [论文页面](https://proceedings.iclr.cc/paper_files/paper/2024/hash/10a6bdcabbd5a3d36b760daa295f63c1-Abstract-Conference.html) | [PDF](https://proceedings.iclr.cc/paper_files/paper/2024/file/10a6bdcabbd5a3d36b760daa295f63c1-Paper-Conference.pdf) |
| G-Retriever | NeurIPS 2024 | 图谱与多跳关系 | 扩展 | [论文页面](https://proceedings.nips.cc/paper_files/paper/2024/hash/efaf1c9726648c8ba363a5c927440529-Abstract-Conference.html) | [PDF](https://proceedings.nips.cc/paper_files/paper/2024/file/efaf1c9726648c8ba363a5c927440529-Paper-Conference.pdf) |
| Self-RAG | ICLR 2024 | 证据检索与核验 | 扩展 | [论文页面](https://proceedings.iclr.cc/paper_files/paper/2024/hash/25f7be9694d7b32d5cc670927b8091e1-Abstract-Conference.html) | [PDF](https://proceedings.iclr.cc/paper_files/paper/2024/file/25f7be9694d7b32d5cc670927b8091e1-Paper-Conference.pdf) |
| LayoutLMv2 | ACL-IJCNLP 2021 | 文档与关系抽取 | 扩展 | [论文页面](https://aclanthology.org/2021.acl-long.201/) | [PDF](https://aclanthology.org/2021.acl-long.201.pdf) |
| SciREX | ACL 2020 | 文档与关系抽取 | 扩展 | [论文页面](https://aclanthology.org/2020.acl-main.670/) | [PDF](https://aclanthology.org/2020.acl-main.670.pdf) |

## 1. ReAct — ICLR 2023

**标题：** ReAct: Synergizing Reasoning and Acting in Language Models

**作者：** Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, Yuan Cao

[论文页面](https://openreview.net/forum?id=WE_vluYUL-X)；[公开全文PDF](https://arxiv.org/pdf/2210.03629v3)；[作者代码](https://github.com/ysymyth/ReAct)

- **论文内容：** 将任务规划与外部动作交替进行，依据工具返回的信息继续处理任务。
- **项目可借鉴之处：** 借鉴查询证据、读取价格、调用计算工具再生成报告的编排方式。
- **适用边界：** 论文实验不是半导体投研；采用这种编排不能证明产业因果关系或财务结论正确。
- **建议阅读成员：** B、D
- **发表核验：** 作者代码仓库标注ICLR 2023；arXiv页面说明v3为ICLR camera-ready版本。OpenReview页面本次访问遇到浏览器验证，因此同时提供作者仓库与定版原文。 [核验来源](https://github.com/ysymyth/ReAct)

## 2. RAG — NeurIPS 2020

**标题：** Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks

**作者：** Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela

[论文页面](https://papers.nips.cc/paper_files/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html)；[公开全文PDF](https://proceedings.nips.cc/paper/2020/file/6b493230205f780e1bc26945df7481e5-Paper.pdf)

- **论文内容：** 结合外部文档检索与文本生成，使模型能够利用检索到的知识回答问题。
- **项目可借鉴之处：** 为公告、财报和材料资料建立可检索证据库；保存文档及页码。
- **适用边界：** 原方法涉及模型训练；首版可借鉴检索与生成的分工，不必复现全部训练。检索到资料也不保证引用正确。
- **建议阅读成员：** B、D
- **发表核验：** NeurIPS正式论文集标注NeurIPS 2020；arXiv作者页面也标注Accepted at NeurIPS 2020。 [核验来源](https://papers.nips.cc/paper_files/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html)

## 3. FinQA — EMNLP 2021

**标题：** FinQA: A Dataset of Numerical Reasoning over Financial Data

**作者：** Zhiyu Chen, Wenhu Chen, Charese Smiley, Sameena Shah, Iana Borova, Dylan Langdon, Reema Moussa, Matt Beane, Ting-Hao Huang, Bryan Routledge, William Yang Wang

[论文页面](https://aclanthology.org/2021.emnlp-main.300/)；[公开全文PDF](https://aclanthology.org/2021.emnlp-main.300.pdf)；[作者代码](https://github.com/czyssrs/FinQA)

- **论文内容：** 提供财报问答数据及专家标注的数值推理程序，用于研究多步金融计算。
- **项目可借鉴之处：** 设计证据、输入参数、公式、计算程序和结果一起保存的计算模块；借鉴执行准确率评价。
- **适用边界：** 财报问答不等于事件冲击预测；材料成本和利润传导公式仍需团队给出依据。
- **建议阅读成员：** A、B、D
- **发表核验：** ACL Anthology列入EMNLP 2021主会正式论文集。 [核验来源](https://aclanthology.org/2021.emnlp-main.300/)

## 4. TAT-QA — ACL-IJCNLP 2021

**标题：** TAT-QA: A Question Answering Benchmark on a Hybrid of Tabular and Textual Content in Finance

**作者：** Fengbin Zhu, Wenqiang Lei, Youcheng Huang, Chao Wang, Shuo Zhang, Jiancheng Lv, Fuli Feng, Tat-Seng Chua

[论文页面](https://aclanthology.org/2021.acl-long.254/)；[公开全文PDF](https://aclanthology.org/2021.acl-long.254.pdf)

- **论文内容：** 联合财报表格与相关文本提取证据，再使用符号运算获得数值答案。
- **项目可借鉴之处：** 帮助设计表格与正文关联、金额单位与数量级处理、混合证据数值问答。
- **适用边界：** 结构化财报问答数据与原始PDF解析是不同环节；不能将该数据集当成通用PDF解析器。
- **建议阅读成员：** A、B、D
- **发表核验：** ACL Anthology列入ACL-IJCNLP 2021主会长论文集。 [核验来源](https://aclanthology.org/2021.acl-long.254/)

## 5. StructGPT — EMNLP 2023

**标题：** StructGPT: A General Framework for Large Language Model to Reason over Structured Data

**作者：** Jinhao Jiang, Kun Zhou, Zican Dong, Keming Ye, Xin Zhao, Ji-Rong Wen

[论文页面](https://aclanthology.org/2023.emnlp-main.574/)；[公开全文PDF](https://aclanthology.org/2023.emnlp-main.574.pdf)；[作者代码](https://github.com/RUCaibox/StructGPT)

- **论文内容：** 通过专门接口读取表格、数据库和知识图谱，迭代执行读取与推理。
- **项目可借鉴之处：** 直接参考B向D提供关系查询、价格查询和参数查询工具的接口设计。
- **适用边界：** 模型应读取已定义的接口；工具输出的事实来源、单位检查和权限仍需独立实现。
- **建议阅读成员：** B、D
- **发表核验：** ACL Anthology列入EMNLP 2023主会正式论文集；作者字段沿用论文集元数据。 [核验来源](https://aclanthology.org/2023.emnlp-main.574/)

## 6. ALCE — EMNLP 2023

**标题：** Enabling Large Language Models to Generate Text with Citations

**作者：** Tianyu Gao, Howard Yen, Jiatong Yu, Danqi Chen

[论文页面](https://aclanthology.org/2023.emnlp-main.398/)；[公开全文PDF](https://aclanthology.org/2023.emnlp-main.398.pdf)；[作者代码](https://github.com/princeton-nlp/ALCE)

- **论文内容：** 研究检索证据并生成带引用文本的系统，评估答案正确性与引用质量等维度。
- **项目可借鉴之处：** 评价报告关键结论是否有引用、引用能否支持结论，而不只检查有没有链接。
- **适用边界：** 引用评价不能替代材料知识和财务逻辑审核；原实验不覆盖本项目的成本传导。
- **建议阅读成员：** A、B、D
- **发表核验：** ACL Anthology列入EMNLP 2023主会正式论文集。 [核验来源](https://aclanthology.org/2023.emnlp-main.398/)

## 7. ConvFinQA — EMNLP 2022

**标题：** ConvFinQA: Exploring the Chain of Numerical Reasoning in Conversational Finance Question Answering

**作者：** Zhiyu Chen, Shiyang Li, Charese Smiley, Zhiqiang Ma, Sameena Shah, William Yang Wang

[论文页面](https://aclanthology.org/2022.emnlp-main.421/)；[公开全文PDF](https://aclanthology.org/2022.emnlp-main.421.pdf)；[作者代码](https://github.com/czyssrs/ConvFinQA)

- **论文内容：** 研究金融对话中跨轮次延续的多步数值推理，并比较神经符号方法与提示方法。
- **项目可借鉴之处：** 设计用户修改涨价幅度、成本占比后重新计算的状态管理，明确保留和更新哪些参数。
- **适用边界：** 先完成单次分析，再考虑多轮对话；历史假设不能悄悄覆盖本轮输入。
- **建议阅读成员：** A、B、D
- **发表核验：** ACL Anthology列入EMNLP 2022主会正式论文集。 [核验来源](https://aclanthology.org/2022.emnlp-main.421/)

## 8. Think-on-Graph — ICLR 2024

**标题：** Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph

**作者：** Jiashuo Sun, Chengjin Xu, Lumingyuan Tang, Saizhuo Wang, Chen Lin, Yeyun Gong, Lionel Ni, Heung-Yeung Shum, Jian Guo

[论文页面](https://proceedings.iclr.cc/paper_files/paper/2024/hash/10a6bdcabbd5a3d36b760daa295f63c1-Abstract-Conference.html)；[公开全文PDF](https://proceedings.iclr.cc/paper_files/paper/2024/file/10a6bdcabbd5a3d36b760daa295f63c1-Paper-Conference.pdf)；[作者代码](https://github.com/IDEA-FinAI/ToG)

- **论文内容：** 让大模型在知识图谱上逐步探索实体和关系，寻找支持答案的多跳路径。
- **项目可借鉴之处：** 借鉴从树脂到光刻胶再到相关企业的路径检索，并将每条关系的证据返回给报告模块。
- **适用边界：** 图谱可达性不等于经济因果效应，更不能直接作为成本转嫁系数。
- **建议阅读成员：** B、C、D、E
- **发表核验：** ICLR正式论文集标注ICLR 2024 Conference；作者字段沿用论文集元数据。 [核验来源](https://proceedings.iclr.cc/paper_files/paper/2024/hash/10a6bdcabbd5a3d36b760daa295f63c1-Abstract-Conference.html)

## 9. G-Retriever — NeurIPS 2024

**标题：** G-Retriever: Retrieval-Augmented Generation for Textual Graph Understanding and Question Answering

**作者：** Xiaoxin He, Yijun Tian, Yifei Sun, Nitesh V. Chawla, Thomas Laurent, Yann LeCun, Xavier Bresson, Bryan Hooi

[论文页面](https://proceedings.nips.cc/paper_files/paper/2024/hash/efaf1c9726648c8ba363a5c927440529-Abstract-Conference.html)；[公开全文PDF](https://proceedings.nips.cc/paper_files/paper/2024/file/efaf1c9726648c8ba363a5c927440529-Paper-Conference.pdf)

- **论文内容：** 从带文本属性的图中检索相关部分，再进行图问答和生成。
- **项目可借鉴之处：** 借鉴按任务取出相关产业子图及证据，减少向模型传入整张图的开销。
- **适用边界：** 原方法包含图模型及微调；首版可采用简单子图查询，不能声称复现了论文方法。
- **建议阅读成员：** B、C、D
- **发表核验：** NeurIPS正式论文集标注NeurIPS 2024 Main Conference Track。 [核验来源](https://proceedings.nips.cc/paper_files/paper/2024/hash/efaf1c9726648c8ba363a5c927440529-Abstract-Conference.html)

## 10. Self-RAG — ICLR 2024

**标题：** Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection

**作者：** Akari Asai, Zeqiu Wu, Yizhong Wang, Avi Sil, Hannaneh Hajishirzi

[论文页面](https://proceedings.iclr.cc/paper_files/paper/2024/hash/25f7be9694d7b32d5cc670927b8091e1-Abstract-Conference.html)；[公开全文PDF](https://proceedings.iclr.cc/paper_files/paper/2024/file/25f7be9694d7b32d5cc670927b8091e1-Paper-Conference.pdf)

- **论文内容：** 训练模型按需检索，并借助反思标记评价资料和生成内容。
- **项目可借鉴之处：** 借鉴检索必要性、证据相关性、结论支持情况等检查维度。
- **适用边界：** 仅增加一个自检Prompt不等于实现Self-RAG；原方法需要训练，且自检不能替代外部证据。
- **建议阅读成员：** A、D
- **发表核验：** ICLR正式论文集标注ICLR 2024 Conference；作者字段沿用论文集元数据。 [核验来源](https://proceedings.iclr.cc/paper_files/paper/2024/hash/25f7be9694d7b32d5cc670927b8091e1-Abstract-Conference.html)

## 11. LayoutLMv2 — ACL-IJCNLP 2021

**标题：** LayoutLMv2: Multi-modal Pre-training for Visually-rich Document Understanding

**作者：** Yang Xu, Yiheng Xu, Tengchao Lv, Lei Cui, Furu Wei, Guoxin Wang, Yijuan Lu, Dinei Florencio, Cha Zhang, Wanxiang Che, Min Zhang, Lidong Zhou

[论文页面](https://aclanthology.org/2021.acl-long.201/)；[公开全文PDF](https://aclanthology.org/2021.acl-long.201.pdf)

- **论文内容：** 联合文档文本、版面位置和图像信息学习文档表示。
- **项目可借鉴之处：** 理解扫描件、复杂表格中版面信息的作用，规划必要的OCR及字段定位能力。
- **适用边界：** 不是开箱即用的任意财报解析器；需要OCR、任务适配等环节，首版优先处理文本型PDF。
- **建议阅读成员：** B、D
- **发表核验：** ACL Anthology列入ACL-IJCNLP 2021主会长论文集。 [核验来源](https://aclanthology.org/2021.acl-long.201/)

## 12. SciREX — ACL 2020

**标题：** SciREX: A Challenge Dataset for Document-Level Information Extraction

**作者：** Sarthak Jain, Madeleine van Zuylen, Hannaneh Hajishirzi, Iz Beltagy

[论文页面](https://aclanthology.org/2020.acl-main.670/)；[公开全文PDF](https://aclanthology.org/2020.acl-main.670.pdf)

- **论文内容：** 研究全文范围内的实体与多元关系抽取，包括跨句、跨段的关联。
- **项目可借鉴之处：** 为材料资料整理设计实体、别名、关系及证据标注；提醒关系可能需要全文上下文。
- **适用边界：** 数据来自科学论文，不是半导体供应链；本项目仍需定义自己的关系类型并人工核验。
- **建议阅读成员：** B、C、D、E
- **发表核验：** ACL Anthology列入ACL 2020主会正式论文集。 [核验来源](https://aclanthology.org/2020.acl-main.670/)

## 如何用于计划书

技术方案可分别引用ReAct的工具编排、RAG的外部证据检索、StructGPT的结构化接口、FinQA/TAT-QA的数值计算及ALCE的引用评价。应说明采用的是哪些设计思路，哪些模块实际实现了，避免把“引用论文”写成“复现了完整方法”。

这些论文主要支撑AI和数据系统的技术设计。它们不提供具体企业的树脂成本占比、价格转嫁系数，也不证明政策对企业利润的因果影响。化学材料知识、企业参数及经济传导证据仍需另行核验。本次未将一般材料综述或经济期刊论文混入“顶尖会议”清单。

FinRobot、通用GraphRAG报告和Docling技术报告等虽然可能相关，但本次没有核实其符合上述主会正式发表标准，因此不纳入本清单；这不代表否认其技术价值。

## 引用与维护

- [BibTeX参考文献](references.bib)：可用于论文或LaTeX引用；题名、作者、年份和会议依据本清单，页码等细节请以正式论文集导出的引用为准。
- [结构化元数据](papers.json)：保存会议、原文、核验来源和项目用途。
- `python research/build_index.py`：从元数据重新生成本页和BibTeX，只使用标准库，不会联网或下载PDF。

正文表述和翻译为本项目整理；论文版权与代码许可证分别归原权利人或原项目。引用及复用代码时保留来源并检查相应许可证。

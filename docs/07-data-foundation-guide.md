# 数据导入与证据查询

更新日期：2026-10-08。本指南说明当前程序的环境、PDF / CSV 导入、数据字典及证据定位。关系、价格、财务指标和参数查询见[业务查询工具说明](08-business-query-tools.md)。

## 1. 已有功能

| 模块 | 当前行为 |
| --- | --- |
| 工程入口 | Python包、cli.py、依赖版本、演示脚本和检查 |
| SQLite | 文档、证据、对象、企业、关系、价格、参数、财务指标八张表；外键和文件级事务 |
| PDF | 读取文本PDF，逐页保存正文，保存1起始PDF页序号；不可提取页输出提示 |
| CSV | 六类模板；校验表头、编号、类型、日期、规格、数字及引用；任一记录失败整份入库回滚 |
| 查询 | 中文/英文关键词、多关键词AND、文件筛选、公开日期截止、数量上限；JSON输出 |
| 来源 | 保存原文件副本、SHA-256、原始文件名、来源URL和公开日期；CSV可关联PDF页 |
| 导入日志 | 成功导入记录保存为imports.jsonl，含UTC时间、数据库位置、操作和摘要 |

数据库登记的fact表示用户提供的真实资料类别，不代表程序已核实内容。verification_status也由资料负责人填写，程序只校验枚举，不代替人工审核。演示文件为demo，演示数值为scenario。

## 2. 环境与快速演示

验证环境：Windows、Python 3.12.14、pypdf 6.10.0、SQLite（随Python）、unittest（标准库）。没有额外服务、API密钥或模型费用。

普通Python环境可按以下PowerShell命令安装依赖；该安装方法提供给队友，当前机器使用已安装pypdf的解释器验证了代码。

```powershell
cd 'D:\Desktop\semiconductor-impact-agent'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe examples/run_demo.py --db data/processed/phase1-demo.sqlite --output outputs/phase1-demo-result.json
.\.venv\Scripts\python.exe cli.py --db data/processed/phase1-demo.sqlite query '树脂'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

当前机器也可直接使用已验证的解释器，不需重新安装：

```powershell
& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' examples/run_demo.py --db data/processed/phase1-demo.sqlite --output outputs/phase1-demo-result.json
& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' cli.py --db data/processed/phase1-demo.sqlite query '树脂'
```

演示用一份自建两页PDF和六份CSV，包含虚构的树脂、光刻胶和企业。预期入库为7份文件、11条证据、3个对象、1家企业、2条关系、2条价格、1个参数和1个财务指标。再次运行同一数据库返回duplicate，记录数不变。

## 3. 导入自己的资料

以下命令用python表示当前已安装依赖的解释器。CLI的全局--db参数写在子命令之前；不填时默认data/processed/agent.sqlite，建议真实资料和演示数据使用不同数据库。

```powershell
python cli.py --db data/processed/real.sqlite init
python cli.py --db data/processed/real.sqlite import-pdf 'data/raw/report.pdf' --document-id REPORT_001 --published-on 2026-09-30 --source-url 'https://example.com/report.pdf' --data-kind fact
python cli.py --db data/processed/real.sqlite import-csv 'data/raw/entities.csv' --table entities --published-on 2026-10-08 --data-kind fact
python cli.py --db data/processed/real.sqlite import-csv 'data/raw/companies.csv' --table companies --published-on 2026-10-08 --data-kind fact
python cli.py --db data/processed/real.sqlite import-csv 'data/raw/material_relations.csv' --table relations --published-on 2026-10-08 --data-kind fact
python cli.py --db data/processed/real.sqlite import-csv 'data/raw/prices.csv' --table prices --published-on 2026-10-08 --data-kind fact
python cli.py --db data/processed/real.sqlite import-csv 'data/raw/calculation_parameters.csv' --table parameters --published-on 2026-10-08 --data-kind fact
python cli.py --db data/processed/real.sqlite import-csv 'data/raw/metrics.csv' --table metrics --published-on 2026-10-08 --data-kind fact
```

上述report.pdf及URL仅为路径用法示意，不是现有数据源。先从templates复制表头填写真实资料；不直接修改模板。

published_on填写资料对外公开可用的日期，不能以导入当天替代未知发布日期。未知时省略，但该文件不会进入--as-of查询。整理CSV自己的可用日期和引用PDF的公开日期都参与截止检查，这不是已经完成的历史回测。

同一文件字节哈希只登记一次。内容相同但文件改名仍视为重复；不覆盖已有来源/日期，不允许将相同内容在fact和demo间重新标记。纠正错误文件需先修订CSV，再使用新数据库或新的对象编号；当前没有覆盖更新/删除命令。

## 4. CSV数据字典

所有表均可加入source_document_id、source_page、verification_status三个字段；前两个可以一起为空（仅追溯到CSV），或者一起指向已导入PDF的有效页。PDF页序号从1开始，包含封面，与印刷页码可能不同。

| --table | 模板 | 必填列 | 可选列（除通用列外） |
| --- | --- | --- | --- |
| entities | entities.csv | entity_id, entity_type, name | grade, aliases |
| companies | companies.csv | company_id, company_name, industry_stage | security_code |
| relations | material_relations.csv | relation_id, upstream_id, downstream_id, relation_type | upstream_name, downstream_name, material_grade, valid_from, valid_to |
| prices | prices.csv | material_id, grade, date, price, unit, currency, price_basis | material_name, source_url, value_type, assumption_note |
| parameters | calculation_parameters.csv | parameter_id, parameter_name, value, unit, period, value_type | company_id, product_id, assumption_note |
| metrics | metrics.csv | metric_id, company_id, metric_name, period, value, unit, currency | value_type, assumption_note |

- 编号使用1～128字符的ASCII字母、数字、下划线、点、冒号或短横线。
- entity_type为company/material/product/process。关系端点必须先存在；不自动推断关系类型的产业含义。
- CSV按UTF-8读取，允许BOM；拒绝重复/未知表头、必填空值及列数不匹配。
- 一个material对象对应一个grade；价格等级须与该对象匹配。currency要求三位大写字母（如CNY），不进行汇率转换或币种真实性核验。
- 参数须至少指定company_id或product_id之一。关系填写material_grade时须有材料端点并与其登记等级一致；两端都是材料时该字段指上游材料等级。
- prices的unit为报价分母单位，例如kg配合CNY表示元/kg；metrics的unit为数值单位，例如元。price_basis需解释采购价、销售价或其他口径，不自动换算。
- 日期为YYYY-MM-DD；数字须为有限十进制，价格不能为负；原料成本占比raw_material_cost_share要求unit=ratio且值在0～1之间。
- 数字按ASCII十进制/科学计数法读取，拒绝千分位逗号、下划线和全角数字；fact文件不能引用demo对象。
- value_type为fact/estimate/scenario。估算和情景需assumption_note；demo数值只接受scenario。参数表必填value_type，价格/指标未填写时依据data_kind默认fact或scenario。
- verification_status为空默认为pending；可以填写verified，但其含义是人工核验结果。
- CSV中的source_url（价格表可选列）保留在记录证据正文；CLI的--source-url是整个文件来源。当前不下载URL，也不判断链接内容是否支持该数字。

原文件副本在数据库同目录的sources/内，名字为完整内容哈希。失败CSV不会留下数据库记录，但可能保留未被数据库引用的文件副本；这是原始快照，不代表导入成功。

2026-10-08审查后，查询、文档查看和重复导入均会核对返回/引用原文件的哈希。副本缺失或被修改时返回明确错误，需恢复原件后继续；不会静默生成新的假证据。两个演示脚本的--output须为.json，不能覆盖数据库或sources中的副本；直接脚本运行和python -m examples.run_demo / examples.run_query_demo均已验证。

## 5. 查询与定位

```powershell
python cli.py --db data/processed/phase1-demo.sqlite query '树脂'
python cli.py --db data/processed/phase1-demo.sqlite query 'cost_share' --document-id DEMO_PDF
python cli.py --db data/processed/phase1-demo.sqlite query '树脂' --as-of 2026-10-08 --limit 5
python cli.py --db data/processed/phase1-demo.sqlite document DEMO_PDF
python cli.py --db data/processed/phase1-demo.sqlite evidence '<查询结果中的evidence_id>'
python cli.py --db data/processed/phase1-demo.sqlite stats
```

evidence命令中的占位符须替换为前一步查询实际返回的编号。查询结果包含evidence_id、text、original_name、file_path、pdf_page或csv_row、published_on、data_kind；CSV引用PDF时另有supporting_document_id、supporting_pdf_page、supporting_file_path。打开file_path查看直接原始文件；打开supporting_file_path并跳到supporting_pdf_page核对整理数据的出处。

csv_row是CSV记录序号，表头视为第1条记录，首条数据为2；带引号的多行字段或空白行会使记录序号与文本编辑器物理行号不同。PDF按页保存，一个页面是一条证据，未拆句或按语义分块。

多关键词以空格分隔，须全部出现在同一证据文本中；查询是字面子串匹配，不是向量检索。limit为1～100条，返回count表示本次返回数量。无命中返回空列表。--as-of仅过滤资料可用日期；业务价格查询同时检查观测日期，财务与参数查询按期间及口径精确匹配，见工具指南。

## 6. 检查与边界

使用已安装固定依赖的解释器执行：

```powershell
python -m unittest discover -s tests -v
python scripts/audit_workspace.py --output outputs/audit/workspace-audit.json
```

2026-10-08 验证的完整套件为50项，覆盖导入、来源定位、事务回滚、重复导入、业务查询、日期与口径、过滤规则、文件哈希、超时保护、CLI及演示脚本。维护检查核验源码语法、CSV模板、论文元数据、现有数据库和原文件哈希。

当前支持单机、小批量本地文件（每份不超过25 MiB）。关系路径、价格、财务指标和参数查询已实现；OCR、PDF表格识别、自动采集、DOCX导入、成本计算、大模型、HTTP服务、网页和完整运行回放尚未实现。imports.jsonl仅记录成功的新文件导入，重复/失败导入及查询没有完整操作日志。

真实供应链关系、化学等级、价格和财务参数仍需资料负责人提供并审核。程序保留类型、核验标记和来源，不能替代行业核验。

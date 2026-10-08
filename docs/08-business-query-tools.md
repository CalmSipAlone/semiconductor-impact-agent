# 业务查询工具操作说明

更新日期：2026-10-08。当前提供五个同步查询工具及CLI入口，用于数据检索和智能体后续接入。暂时没有模型、成本计算和HTTP服务。

## 1. 五个工具

| Python名称 / CLI名称 | 必填输入 | 返回的业务数据 |
| --- | --- | --- |
| search_evidence / search-evidence | 无；query可空 | 原文、来源、PDF页或CSV记录序号；原始证据不等于已核实结论 |
| query_relations / query-relations | entity_id | 有向关系、有限深度路径、端点对象、核验状态和逐条来源 |
| query_prices / query-prices | material_id, grade, unit, currency, price_basis | 精确口径的价格记录；日期区间、类型、冲突及来源 |
| query_metrics / query-metrics | company_id, metric_name, period, unit, currency | 指定企业和报告期的指标，不自动换算或补齐 |
| query_parameters / query-parameters | period；company_id或product_id至少一个 | 参数及适用对象、单位、参数性质、假设说明和来源 |

Python对象：`QueryTools(Database(path))`。直接调用使用`tools.call(name, **arguments)`，或者用`tools.registry()`取得五个普通Python可调用对象。不依赖D选用哪种智能体框架。

工具返回始终包含五个字段：

```json
{
  "status": "ok",
  "data": {},
  "evidence_ids": [],
  "warnings": [],
  "error": null
}
```

- `ok`：该次请求完成；不代表数据是事实、行业正确性已证实或整个数据库覆盖充分。
- `partial`：缺少匹配资料、对象被筛掉、记录/遍历数量限制、数值冲突或混合参数性质。数据中的truncated/conflicts/missing_fields及warnings说明原因。缺失时error带明确代码；截断/冲突可以为null。
- `error`：未知工具、非法参数、未知对象、数据库错误或执行超时；error含code/message/retryable。
- evidence_ids包含返回记录及对象的直接证据，以及有可提取文本的关联PDF页证据。source里保留原文件路径、SHA-256、公开日期和定位信息；无文本PDF页仍可定位原文件，但没有伪造正文证据。

数值仍为十进制字符串；调用方不得将无数据解释为0。CLI正常和partial返回退出码0，error返回1；命令行参数语法错误沿用argparse的退出码2。

返回结果涉及的原文件会做SHA-256校验。缺失、被修改或路径不在证据目录内时，统一工具返回error / SOURCE_INTEGRITY_ERROR，不把旧的数据库提取内容当作可正常追溯的证据。

## 2. 默认筛选和显式放宽

四类业务工具默认：`include_pending=False`、`include_demo=False`；三个数值工具额外默认`value_type='fact'`。这些条件同时检查所查对象和业务记录的来源；参数查询还会检查记录引用的其他企业/产品。

因此当前虚构演示库用默认业务查询会返回NO_ELIGIBLE_ENTITY。这是正常结果。演示时须显式给出`include_pending=True`、`include_demo=True`、`value_type='scenario'`；返回warnings保留这些性质。

`fact`与`verified`都是导入者提供的标记，程序不替代A/C/E核验。数值的value_type可以是fact/estimate/scenario/all；all会保留类型，混合类型返回partial，不能当作一个事实价格序列合并。

search_evidence查原始证据，没有统一的业务记录核验字段。它默认排除demo，但不会声称检索出来的原文已经人工核验。

## 3. 日期与口径

- 所有工具可用as_of，按直接来源和关联PDF的公开可用日期过滤；未来或未知发布日期不进入结果。对象本身的来源同样参与过滤。
- 价格还限制观测日期date不晚于as_of；start_date/end_date为闭区间。没有as_of时不限定历史可用性。
- 关系按as_of检查valid_from/valid_to，空值表示没有已登记边界；未指定as_of时可以查询历史/当前全部记录，不能据此宣称关系当前仍有效。
- 财务period和参数period按原字符串精确匹配，暂时不自动解释季度/财年、累计/单季或期间截止日。历史可用性以来源公开日期为准。
- 价格等级、单位、币种、报价口径精确匹配，不把kg/tonne、yuan/元、采购/销售报价自动视为同一口径。输入币种须为三位大写字母，程序不维护币种代码表。
- 同一范围下出现不同数值，保留全部来源并列入conflicts，不自动挑最新或平均；100与100.0按同一数值处理。
- 价格没有自动计算涨跌幅，关系没有自动生成成本权重，也没有把路径作为因果证据。

## 4. 关系路径与数量边界

direction可为downstream/upstream/both；depth为1～4，默认2。downstream沿原始upstream_id→downstream_id走，upstream反向走，both允许任一方向。返回relation记录保留原始方向，path记录的是遍历顺序，反向路径不意味着存在新的反向供应关系。

返回路径包含每个可达前缀，例如A→B、A→B→C。路径不重复对象；图中循环会跳过并提示。relation_type为单一类型的精确筛选，应用于路径每条边；不填则保留多种关系。

limit为1～100，关系查询默认30（Python）/20（CLI），其他数值查询默认20、证据查询默认10。关系limit限制路径条数，每个节点最多读取500条邻接边；触及限制则truncated=true并返回partial。证据/数值多取一条用于检查截断；冲突检查只覆盖返回的子集，不保证检查了库中所有候选。

查询使用一次SQLite读事务保存单次响应的一致视图。SQL执行和关系遍历有约5秒保护，数据库锁等待沿用连接的10秒设置；这不是带硬取消的异步任务服务。当前没有完整查询审计日志或可供跨工具共享的固定数据快照。

## 5. 本机演示

先进入工程目录，解释器安装pypdf 6.10.0（见数据导入指南），然后执行：

```powershell
cd 'D:\Desktop\semiconductor-impact-agent'
python examples/run_query_demo.py --output outputs/phase2-query-demo-result.json
python cli.py --db data/processed/phase2-demo.sqlite query-relations MATERIAL_M1 --depth 2 --include-demo --include-pending
python cli.py --db data/processed/phase2-demo.sqlite query-prices MATERIAL_M1 --grade DEMO_GRADE --unit kg --currency CNY --price-basis demo_assumption --value-type scenario --include-demo --include-pending --as-of 2026-10-08
python cli.py --db data/processed/phase2-demo.sqlite query-metrics COMPANY_C1 --metric-name revenue --period 2026-DEMO --unit yuan --currency CNY --value-type scenario --include-demo --include-pending
python cli.py --db data/processed/phase2-demo.sqlite query-parameters --company-id COMPANY_C1 --product-id PRODUCT_P1 --period 2026-DEMO --parameter-name raw_material_cost_share --value-type scenario --include-demo --include-pending
python cli.py --db data/processed/phase2-demo.sqlite search-evidence '树脂' --include-demo
```

本机可将python替换为`& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'`。

预期演示返回：1条材料路径、2条价格、1条营收指标、1条原料成本占比参数和4条中文证据；另演示默认过滤和单位不匹配两个partial结果。全部为虚构数据，不计算财务影响。

## 6. D的Python接入方式

从src运行或安装项目包后：

```python
from semiconductor_agent.storage import Database
from semiconductor_agent.tools import QueryTools

tools = QueryTools(Database('data/processed/phase2-demo.sqlite')).registry()
result = tools['query_prices'](
    material_id='MATERIAL_M1', grade='DEMO_GRADE', unit='kg',
    currency='CNY', price_basis='demo_assumption', as_of='2026-10-08',
    include_demo=True, include_pending=True, value_type='scenario',
)
# D检查status、warnings、error，并保留evidence_ids和source定位。
# 即使status=ok，也不能将scenario参数叙述为企业披露值。
```

现有registry是同步Python函数集合，尚未包含特定模型的函数调用JSON Schema、MCP或HTTP适配层。D接入前双方仍需确认模型工具格式、调用预算及错误处理；本阶段不声称大模型联调完成。

## 7. 验证

使用已安装固定依赖的解释器执行：

```powershell
python -m unittest discover -s tests -v
python scripts/audit_workspace.py --output outputs/audit/workspace-audit.json
```

2026-10-08 完整套件50项全部通过，包括19项数据基础检查、21项业务查询检查和10项回归检查。覆盖关系遍历、价格精确口径、公开日期、来源页、冲突、情景筛选、参数适用范围、统一错误、只读行为、超时保护及CLI。

独立新数据库演示已完成从PDF / CSV导入到五类查询的完整流程。默认过滤和单位不匹配返回partial属于预期行为。维护检查还会核验源码、模板、论文元数据、现有数据库及原件哈希。

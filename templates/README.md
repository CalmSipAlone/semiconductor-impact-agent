# 资料交付模板

这些CSV只包含表头，尚未填写真实企业、材料、价格或参数。请使用UTF-8编码（允许BOM）。当前导入器支持以下模板，实际操作见[操作说明](../docs/07-data-foundation-guide.md)。

- entities.csv：材料、产品、工艺及企业的固定编号、名称与等级；先登记关系端点。
- companies.csv：企业名单与产业环节，C负责内容核验；会同时登记company类别对象。
- material_relations.csv：材料、产品、工艺或企业之间的关系，C/E负责核验。
- prices.csv：具体规格的价格记录，资料负责人和B共同检查口径。
- calculation_parameters.csv：公式需要的参数，A负责定义，C/E核验专业适用性。
- metrics.csv：企业财务指标和报告期间，A负责核验。

source_document_id和source_page指向已导入PDF的文件编号和1起始页序号，须成对填写或同时留空。verification_status可填写pending或verified，空值默认为pending；value_type可填写fact、estimate或scenario。estimate/scenario必须有assumption_note。没有依据的可选字段留空；缺少必填字段时先补充资料，导入器不会替用户编造或填0。

导入顺序为PDF → entities → companies → material_relations → prices / calculation_parameters / metrics。同一个材料编号当前对应一个grade；不同等级请分配不同编号。aliases中的多个别名用竖线分隔。

参数必须至少填写company_id或product_id之一。关系的material_grade填写材料端点的等级（两端都是材料时指上游），与已登记等级一致。数值使用ASCII十进制或科学计数法，不接受千分位逗号、下划线或全角数字。fact资料不得引用demo对象。

材料“用于生产”与企业“已证实供货”应使用不同relation_type。grade填写具体材料等级；price_basis说明采购价、销售价或其他口径。单位、币种和期间必须能够解释。

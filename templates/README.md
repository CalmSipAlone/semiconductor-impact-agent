# 资料交付模板

这些CSV只包含表头，尚未填写真实企业、材料、价格或参数。请使用UTF-8编码。

- companies.csv：企业名单与产业环节，C负责内容核验。
- material_relations.csv：材料、产品、工艺或企业之间的关系，C/E负责核验。
- prices.csv：具体规格的价格记录，资料负责人和B共同检查口径。
- calculation_parameters.csv：公式需要的参数，A负责定义，C/E核验专业适用性。

source_document_id和source_page指向可查阅证据。verification_status可填写pending或verified；value_type可填写fact、estimate或scenario。没有依据的字段留空，不填虚构数据。

材料“用于生产”与企业“已证实供货”应使用不同relation_type。grade填写具体材料等级；price_basis说明采购价、销售价或其他口径。单位、币种和期间必须能够解释。

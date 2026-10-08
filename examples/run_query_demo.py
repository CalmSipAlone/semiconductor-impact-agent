"""Demonstrate the unified tools with explicit permission to view fictional data."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
if __package__:
    from .run_demo import run_demo
    from .demo_utils import checked_output
else:
    from run_demo import run_demo
    from demo_utils import checked_output
from semiconductor_agent.storage import Database
from semiconductor_agent.tools import QueryTools


def run_query_demo(db_path=None):
    path = db_path or ROOT / 'data/processed/phase2-demo.sqlite'
    ingestion = run_demo(path)
    tools = QueryTools(Database(path))
    allowed = {'include_demo': True, 'include_pending': True, 'as_of': '2026-10-08'}
    numerical = {**allowed, 'value_type': 'scenario'}
    return {
        'notice': 'Fictional data only; no real company analysis or calculation.',
        'counts': ingestion['counts'],
        'queries': {
            'relations': tools.call('query_relations', entity_id='MATERIAL_M1', **allowed),
            'prices': tools.call('query_prices', material_id='MATERIAL_M1', grade='DEMO_GRADE',
                                 unit='kg', currency='CNY', price_basis='demo_assumption', **numerical),
            'metrics': tools.call('query_metrics', company_id='COMPANY_C1', metric_name='revenue',
                                  period='2026-DEMO', unit='yuan', currency='CNY', **numerical),
            'parameters': tools.call('query_parameters', company_id='COMPANY_C1', product_id='PRODUCT_P1',
                                     parameter_name='raw_material_cost_share', period='2026-DEMO', **numerical),
            'evidence': tools.call('search_evidence', query='树脂', include_demo=True, as_of='2026-10-08'),
            'default_filter': tools.call('query_relations', entity_id='MATERIAL_M1'),
            'missing_price': tools.call('query_prices', material_id='MATERIAL_M1', grade='DEMO_GRADE',
                                        unit='tonne', currency='CNY', price_basis='demo_assumption', **numerical),
        },
    }


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--db')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        output = checked_output(args.output, args.db or ROOT / 'data/processed/phase2-demo.sqlite')
    except ValueError as exc:
        parser.error(str(exc))
    result = json.dumps(run_query_demo(args.db), ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result + '\n', encoding='utf-8')
    print(result)

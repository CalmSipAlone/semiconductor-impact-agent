"""Exercise real ingestion/query code with clearly marked fictional data."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
if __package__:
    from .build_demo_pdf import DEMO_PAGES, write_pdf
    from .demo_utils import checked_output
else:
    from build_demo_pdf import DEMO_PAGES, write_pdf
    from demo_utils import checked_output
from semiconductor_agent.ingest import Importer
from semiconductor_agent.query import EvidenceQuery
from semiconductor_agent.storage import Database


def run_demo(db_path=None):
    database = Database(db_path or ROOT / 'data/processed/demo.sqlite')
    importer = Importer(database)
    folder = ROOT / 'examples/demo_data'
    pdf = folder / 'demo.pdf'
    write_pdf(pdf, DEMO_PAGES)
    options = {'data_kind': 'demo', 'published_on': '2026-10-08'}
    imports = [importer.import_pdf(pdf, document_id='DEMO_PDF', **options)]
    for table, filename in [('entities', 'entities.csv'), ('companies', 'companies.csv'),
                            ('relations', 'material_relations.csv'), ('prices', 'prices.csv'),
                            ('parameters', 'calculation_parameters.csv'), ('metrics', 'metrics.csv')]:
        imports.append(importer.import_csv(folder / filename, table=table, **options))
    return {'data_kind': 'demo', 'notice': 'All entities and figures are fictional demo data.',
            'database': str(database.path), 'imports': imports, 'counts': database.counts(),
            'pdf_query': EvidenceQuery(database).search('cost_share', document_id='DEMO_PDF'),
            'csv_query': EvidenceQuery(database).search('树脂', limit=10)}


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Import fictional data and exercise evidence lookup')
    parser.add_argument('--db', help='Use a separate SQLite database')
    parser.add_argument('--output', help='Also save the JSON result locally')
    args = parser.parse_args()
    try:
        output = checked_output(args.output, args.db or ROOT / 'data/processed/demo.sqlite')
    except ValueError as exc:
        parser.error(str(exc))
    result = json.dumps(run_demo(args.db), ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result + '\n', encoding='utf-8')
    print(result)

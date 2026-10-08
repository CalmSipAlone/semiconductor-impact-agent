import argparse
import json
import sqlite3
import sys

from .errors import DataError
from .ingest import Importer, SPECS
from .query import EvidenceQuery
from .storage import Database
from .tools import QueryTools


def parser():
    root = argparse.ArgumentParser(description='Local evidence ingestion and business query tools')
    root.add_argument('--db', default='data/processed/agent.sqlite', help='SQLite database path')
    commands = root.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Initialize or check the database schema')
    commands.add_parser('stats', help='Count registered documents and data records')
    for command in ['import-pdf', 'import-csv']:
        sub = commands.add_parser(command)
        sub.add_argument('path')
        sub.add_argument('--document-id')
        sub.add_argument('--source-url')
        sub.add_argument('--published-on', help='Public availability date, YYYY-MM-DD')
        sub.add_argument('--data-kind', choices=['fact', 'demo'], default='fact')
        if command == 'import-csv':
            sub.add_argument('--table', choices=list(SPECS), required=True)
    sub = commands.add_parser('query')
    sub.add_argument('text', nargs='?', default='')
    sub.add_argument('--document-id')
    sub.add_argument('--limit', type=int, default=10)
    sub.add_argument('--as-of')
    sub = commands.add_parser('document')
    sub.add_argument('document_id')
    sub = commands.add_parser('evidence')
    sub.add_argument('evidence_id')
    for name in QueryTools.NAMES:
        sub = commands.add_parser(name.replace('_', '-'), help=f'Agent-compatible {name} tool')
        sub.add_argument('--as-of')
        sub.add_argument('--limit', type=int, default=10 if name == 'search_evidence' else 20)
        sub.add_argument('--include-demo', action='store_true')
        if name != 'search_evidence':
            sub.add_argument('--include-pending', action='store_true')
        if name == 'query_relations':
            sub.add_argument('entity_id')
            sub.add_argument('--direction', choices=['upstream', 'downstream', 'both'], default='downstream')
            sub.add_argument('--relation-type')
            sub.add_argument('--depth', type=int, default=2)
        elif name == 'query_prices':
            sub.add_argument('material_id')
            for field in ['grade', 'unit', 'currency', 'price_basis']:
                sub.add_argument('--' + field.replace('_', '-'), required=True)
            sub.add_argument('--start-date')
            sub.add_argument('--end-date')
        elif name == 'query_metrics':
            sub.add_argument('company_id')
            for field in ['metric_name', 'period', 'unit', 'currency']:
                sub.add_argument('--' + field.replace('_', '-'), required=True)
        elif name == 'query_parameters':
            sub.add_argument('--company-id')
            sub.add_argument('--product-id')
            sub.add_argument('--parameter-name')
            sub.add_argument('--period', required=True)
            sub.add_argument('--unit')
        else:
            sub.add_argument('query', nargs='?', default='')
            sub.add_argument('--document-id')
        if name in {'query_prices', 'query_metrics', 'query_parameters'}:
            sub.add_argument('--value-type', choices=['fact', 'estimate', 'scenario', 'all'], default='fact')
    return root


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    args = parser().parse_args(argv)
    database = Database(args.db)
    try:
        if args.command == 'init':
            database.initialize()
            result = {'status': 'ok', 'database': str(database.path), 'schema_version': 1}
        elif args.command == 'stats':
            result = database.counts()
        elif args.command in {'import-pdf', 'import-csv'}:
            options = {key: getattr(args, key) for key in ['document_id', 'source_url', 'published_on', 'data_kind']}
            importer = Importer(database)
            result = importer.import_pdf(args.path, **options) if args.command == 'import-pdf' else importer.import_csv(args.path, table=args.table, **options)
        elif args.command == 'query':
            result = EvidenceQuery(database).search(args.text, document_id=args.document_id, limit=args.limit, as_of=args.as_of)
        elif args.command == 'document':
            result = database.document(args.document_id)
        elif args.command.replace('-', '_') in QueryTools.NAMES:
            arguments = {k: v for k, v in vars(args).items() if k not in {'db', 'command'}}
            result = QueryTools(database).call(args.command.replace('-', '_'), **arguments)
        else:
            result = EvidenceQuery(database).evidence(args.evidence_id)
    except (DataError, OSError, sqlite3.Error, ImportError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get('status') == 'error' else 0

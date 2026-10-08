"""Read-only checks for source syntax, templates, metadata and saved databases."""
import argparse
import ast
import csv
import importlib.metadata
import json
import sqlite3
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from semiconductor_agent.ingest import COMMON, SPECS, _number, iso_date
from semiconductor_agent.storage import Database


def audit():
    result = {'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version,
              'python_files': [], 'templates': [], 'databases': [], 'errors': []}
    skipped = {'.git', '.venv', '__pycache__', 'outputs', 'data', 'build', 'dist', '.local-migration'}
    for path in sorted(ROOT.rglob('*.py')):
        if skipped.intersection(path.relative_to(ROOT).parts) or any(
                part.endswith('.egg-info') for part in path.parts):
            continue
        try:
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
            result['python_files'].append(str(path.relative_to(ROOT)))
        except (OSError, SyntaxError, UnicodeError) as exc:
            result['errors'].append(f'{path}: {exc}')
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    result['project_version'] = project['project']['version']
    try:
        result['pypdf'] = importlib.metadata.version('pypdf')
        if result['pypdf'] != '6.10.0':
            result['errors'].append('Installed pypdf differs from the tested requirements version')
    except importlib.metadata.PackageNotFoundError:
        result['errors'].append('pypdf is not installed')
    template_names = {'entities':'entities.csv','companies':'companies.csv',
                      'relations':'material_relations.csv','prices':'prices.csv',
                      'parameters':'calculation_parameters.csv','metrics':'metrics.csv'}
    for table, name in template_names.items():
        with (ROOT / 'templates' / name).open(encoding='utf-8-sig', newline='') as stream:
            fields = next(csv.reader(stream))
        required, optional = SPECS[table]
        if len(set(fields)) != len(fields) or required - set(fields) or set(fields) - (required | optional | COMMON):
            result['errors'].append(f'Template columns do not match importer: {name}')
        result['templates'].append(name)
    papers = json.loads((ROOT / 'research/papers.json').read_text(encoding='utf-8'))
    if len(papers) != 12 or len({p['id'] for p in papers}) != len(papers):
        result['errors'].append('Paper metadata count or IDs are inconsistent')
    for paper in papers:
        if not paper['track'].startswith('Main conference') or paper['venue'] not in {'ACL','ACL-IJCNLP','EMNLP','ICLR','NeurIPS'}:
            result['errors'].append(f'Unexpected paper classification: {paper["id"]}')
    result['paper_metadata_count'] = len(papers)
    for path in sorted((ROOT / 'data/processed').glob('*.sqlite')):
        report = {'database': path.name, 'errors': []}
        conn = None
        try:
            conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
            conn.row_factory = sqlite3.Row
            with conn:
                conn.execute('BEGIN')
                report['integrity'] = [row[0] for row in conn.execute('PRAGMA integrity_check')]
                report['foreign_key_violations'] = len(conn.execute('PRAGMA foreign_key_check').fetchall())
                report['schema_version'] = conn.execute('PRAGMA user_version').fetchone()[0]
                if report['integrity'] != ['ok'] or report['foreign_key_violations'] or report['schema_version'] != 1:
                    report['errors'].append('Database schema/integrity check failed')
                originals = conn.execute('SELECT * FROM documents').fetchall()
                report['documents_checked'] = len(originals)
                database = Database(path)
                for document in originals:
                    try:
                        database.verify_original(document['stored_path'], document['sha256'])
                        iso_date(document['published_on'], 'published_on')
                    except (ValueError, OSError) as exc:
                        report['errors'].append(str(exc))
                report['unscoped_parameters'] = conn.execute(
                    'SELECT COUNT(*) FROM parameters WHERE company_id IS NULL AND product_id IS NULL').fetchone()[0]
                if report['unscoped_parameters']:
                    report['errors'].append('Parameters without a company/product scope')
                for entity in conn.execute('SELECT entity_id, aliases_json FROM entities'):
                    try:
                        aliases = json.loads(entity['aliases_json'])
                        if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
                            raise ValueError('aliases must be a string list')
                    except (ValueError, TypeError) as exc:
                        report['errors'].append(f'{entity["entity_id"]}: {exc}')
                for table, column in [('prices','price'), ('metrics','value'), ('parameters','value')]:
                    for row in conn.execute(f'SELECT {column} FROM {table}'):
                        try:
                            _number(row[0], column, nonnegative=table == 'prices')
                        except ValueError as exc:
                            report['errors'].append(f'{table}: {exc}')
        except sqlite3.Error as exc:
            report['errors'].append(str(exc))
        finally:
            if conn is not None:
                conn.close()
        result['databases'].append(report)
        result['errors'] += [f'{path.name}: {error}' for error in report['errors']]
    result['status'] = 'ok' if not result['errors'] else 'error'
    result['python_file_count'] = len(result['python_files'])
    return result


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', help='Optional .json report path')
    args = parser.parse_args()
    if args.output and Path(args.output).suffix.lower() != '.json':
        parser.error('Audit output must use .json')
    result = audit()
    data = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).resolve()
        if output.is_relative_to(ROOT / 'data') or output.is_relative_to(ROOT / 'research'):
            parser.error('Audit output cannot overwrite data or research metadata')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(data + '\n', encoding='utf-8')
    print(data)
    raise SystemExit(0 if result['status'] == 'ok' else 1)

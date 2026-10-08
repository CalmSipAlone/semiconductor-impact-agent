import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'examples')]
from build_demo_pdf import DEMO_PAGES, write_pdf
from run_demo import run_demo
from semiconductor_agent.errors import DataError
from semiconductor_agent.ingest import Importer
from semiconductor_agent.query import EvidenceQuery
from semiconductor_agent.storage import Database


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = Database(self.root / 'agent.sqlite')
        self.importer = Importer(self.db)
        self.pdf = write_pdf(self.root / 'demo.pdf', DEMO_PAGES)

    def import_pdf(self, **kwargs):
        return self.importer.import_pdf(self.pdf, document_id='DEMO_PDF', data_kind='demo', **kwargs)

    def csv_file(self, name, fields, rows):
        path = self.root / name
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def entity_file(self, rows):
        return self.csv_file('entities.csv', ['entity_id','entity_type','name','grade'], rows)

    def test_pdf_page_and_original_provenance(self):
        self.import_pdf()
        result = EvidenceQuery(self.db).search('cost_share', document_id='DEMO_PDF')
        self.assertEqual(result['count'], 1)
        item = result['results'][0]
        self.assertEqual(item['pdf_page'], 2)
        self.assertEqual(item['data_kind'], 'demo')
        self.assertEqual(Path(item['file_path']).read_bytes(), self.pdf.read_bytes())
        evidence = EvidenceQuery(self.db).evidence(item['evidence_id'])
        self.assertEqual(evidence['document']['original_name'], 'demo.pdf')

    def test_duplicate_file_does_not_add_records(self):
        self.import_pdf()
        before = self.db.counts()
        self.assertEqual(self.import_pdf()['status'], 'duplicate')
        self.assertEqual(self.db.counts(), before)
        with self.assertRaisesRegex(DataError, 'relabeled'):
            self.importer.import_pdf(self.pdf, data_kind='fact')

    def test_complete_demo_and_repeat_import(self):
        first = run_demo(self.db.path)
        expected = {'documents': 7, 'evidence_chunks': 11, 'entities': 3, 'companies': 1,
                    'relations': 2, 'prices': 2, 'parameters': 1, 'metrics': 1}
        self.assertEqual(first['counts'], expected)
        second = run_demo(self.db.path)
        self.assertEqual(second['counts'], expected)
        self.assertTrue(all(item['status'] == 'duplicate' for item in second['imports']))

    def test_csv_chinese_query_and_pdf_reference(self):
        run_demo(self.db.path)
        results = EvidenceQuery(self.db).search('树脂')['results']
        self.assertTrue(results)
        self.assertTrue(all(r['csv_row'] >= 2 for r in results))
        self.assertTrue(all(r['supporting_document_id'] == 'DEMO_PDF' for r in results))
        self.assertTrue(all(Path(r['supporting_file_path']).exists() for r in results))

    def test_late_csv_error_rolls_back_whole_file(self):
        path = self.entity_file([
            {'entity_id':'M1','entity_type':'material','name':'树脂','grade':'DEMO'},
            {'entity_id':'M2','entity_type':'unknown','name':'bad','grade':'DEMO'},
        ])
        with self.assertRaisesRegex(DataError, 'row 3'):
            self.importer.import_csv(path, table='entities')
        self.assertEqual(self.db.counts()['entities'], 0)
        self.assertEqual(self.db.counts()['documents'], 0)
        self.assertEqual(self.db.counts()['evidence_chunks'], 0)

    def test_csv_bad_header_and_column_count(self):
        file = self.root / 'bad.csv'
        file.write_text('entity_id,entity_type,nmae\nM1,material,resin\n', encoding='utf-8')
        with self.assertRaisesRegex(DataError, 'unknown'):
            self.importer.import_csv(file, table='entities')
        file.write_text('entity_id,entity_type,name\nM1,material,resin,EXTRA\n', encoding='utf-8')
        with self.assertRaisesRegex(DataError, 'column count'):
            self.importer.import_csv(file, table='entities')

    def test_csv_source_page_must_exist(self):
        self.import_pdf()
        path = self.csv_file('entities.csv',
                             ['entity_id','entity_type','name','source_document_id','source_page'],
                             [{'entity_id':'M1','entity_type':'material','name':'树脂',
                               'source_document_id':'DEMO_PDF','source_page':'99'}])
        with self.assertRaisesRegex(DataError, 'out of range'):
            self.importer.import_csv(path, table='entities', data_kind='demo')
        self.assertEqual(self.db.counts()['documents'], 1)

    def test_as_of_excludes_future_and_unknown_publication(self):
        self.import_pdf(published_on='2026-10-08')
        query = EvidenceQuery(self.db)
        self.assertEqual(query.search('resin', as_of='2026-10-07')['count'], 0)
        self.assertGreater(query.search('resin', as_of='2026-10-08')['count'], 0)
        other = write_pdf(self.root / 'unknown.pdf', [['UNIQUE unknown publication']])
        self.importer.import_pdf(other, data_kind='demo')
        self.assertEqual(query.search('UNIQUE', as_of='2026-10-08')['count'], 0)

    def test_as_of_also_checks_supporting_pdf(self):
        self.import_pdf(published_on='2026-10-08')
        path = self.csv_file('entities.csv',
                             ['entity_id','entity_type','name','source_document_id','source_page'],
                             [{'entity_id':'M1','entity_type':'material','name':'树脂',
                               'source_document_id':'DEMO_PDF','source_page':'1'}])
        self.importer.import_csv(path, table='entities', data_kind='demo', published_on='2026-10-01')
        self.assertEqual(EvidenceQuery(self.db).search('树脂', as_of='2026-10-07')['count'], 0)

    def test_blank_pdf_reports_ocr_requirement(self):
        path = write_pdf(self.root / 'blank.pdf', [[]])
        result = self.importer.import_pdf(path)
        self.assertEqual(result['status'], 'needs_ocr')
        self.assertEqual(result['evidence_count'], 0)
        self.assertTrue(result['warnings'])

    def test_corrupt_pdf_has_no_database_records(self):
        path = self.root / 'corrupt.pdf'
        path.write_bytes(b'%PDF-1.4 not a readable file')
        with self.assertRaisesRegex(DataError, 'parsing failed'):
            self.importer.import_pdf(path)
        self.assertEqual(self.db.counts()['documents'], 0)

    def test_sql_foreign_keys_are_enabled(self):
        self.db.initialize()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as conn:
                conn.execute("INSERT INTO companies VALUES ('missing',NULL,'test')")

    def test_query_literal_wildcards_and_sql_input(self):
        self.import_pdf()
        self.assertEqual(EvidenceQuery(self.db).search('%')['count'], 0)
        self.assertEqual(EvidenceQuery(self.db).search("' OR 1=1 --")['count'], 0)
        with self.assertRaises(DataError):
            EvidenceQuery(self.db).search('resin', limit=0)

    def test_numeric_nan_and_grade_mismatch_are_rejected(self):
        run_demo(self.db.path)
        fields = ['material_id','grade','date','price','unit','currency','price_basis','value_type','assumption_note']
        row = {'material_id':'MATERIAL_M1','grade':'DEMO_GRADE','date':'2026-10-08',
               'price':'NaN','unit':'kg','currency':'CNY','price_basis':'demo',
               'value_type':'scenario','assumption_note':'demo'}
        path = self.csv_file('new_prices.csv', fields, [row])
        before = self.db.counts()
        with self.assertRaisesRegex(DataError, 'finite decimal'):
            self.importer.import_csv(path, table='prices', data_kind='demo')
        row.update(price='100', grade='OTHER')
        path = self.csv_file('new_prices.csv', fields, [row])
        with self.assertRaisesRegex(DataError, 'grade'):
            self.importer.import_csv(path, table='prices', data_kind='demo')
        self.assertEqual(self.db.counts(), before)

    def test_unknown_relation_endpoint_is_rejected(self):
        path = self.csv_file('relations.csv', ['relation_id','upstream_id','downstream_id','relation_type'],
                             [{'relation_id':'R1','upstream_id':'missing','downstream_id':'other','relation_type':'used_to_make'}])
        with self.assertRaisesRegex(DataError, 'Unknown entity'):
            self.importer.import_csv(path, table='relations')
        self.assertEqual(self.db.counts()['relations'], 0)

    def test_cli_success_and_failure_exit_codes(self):
        command = [sys.executable, str(ROOT / 'cli.py'), '--db', str(self.db.path)]
        success = subprocess.run([*command, 'init'], capture_output=True, encoding='utf-8')
        self.assertEqual(success.returncode, 0)
        self.assertEqual(json.loads(success.stdout)['status'], 'ok')
        failure = subprocess.run([*command, 'document', 'unknown'], capture_output=True, encoding='utf-8')
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(json.loads(failure.stdout)['status'], 'error')

    def test_log_failure_does_not_misreport_committed_import(self):
        with patch.object(self.db, 'log', side_effect=OSError('disk unavailable')):
            result = self.import_pdf()
        self.assertEqual(result['status'], 'imported')
        self.assertEqual(self.db.counts()['documents'], 1)
        self.assertIn('Import committed', result['warnings'][0])

    def test_demo_pdf_cannot_support_fact_csv(self):
        self.import_pdf()
        path = self.csv_file('entities.csv',
                             ['entity_id','entity_type','name','source_document_id','source_page'],
                             [{'entity_id':'M1','entity_type':'material','name':'树脂',
                               'source_document_id':'DEMO_PDF','source_page':'1'}])
        with self.assertRaisesRegex(DataError, 'Demo PDF evidence'):
            self.importer.import_csv(path, table='entities', data_kind='fact')
        self.assertEqual(self.db.counts()['entities'], 0)

    def test_csv_locator_is_record_number_with_multiline_field(self):
        path = self.entity_file([
            {'entity_id':'M1','entity_type':'material','name':'resin\nmultiline','grade':'DEMO'},
            {'entity_id':'M2','entity_type':'material','name':'second resin','grade':'DEMO'},
        ])
        self.importer.import_csv(path, table='entities', data_kind='demo')
        result = EvidenceQuery(self.db).search('second')['results'][0]
        self.assertEqual(result['csv_row'], 3)


if __name__ == '__main__':
    unittest.main()

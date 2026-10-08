"""Regression cases identified during the full workspace review."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

import test_query_tools as fixtures
from semiconductor_agent.errors import DataError
from semiconductor_agent.ingest import _number, iso_date
from semiconductor_agent.query import EvidenceQuery
from run_demo import run_demo


class AuditRegressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.QueryToolTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db = self.fixture.db

    def test_parameters_require_an_applicable_object(self):
        before = self.db.counts()
        with self.assertRaisesRegex(DataError, 'company_id or product_id'):
            self.fixture.load('parameters', [{'parameter_id':'ORPHAN', 'parameter_name':'share',
                                             'value':'0.3','unit':'ratio','period':'Q3','value_type':'fact'}])
        self.assertEqual(self.db.counts(), before)

    def test_relation_grade_must_match_material_endpoint(self):
        with self.assertRaisesRegex(DataError, 'grade'):
            self.fixture.load('relations', [{'relation_id':'BAD_GRADE','upstream_id':'M1','downstream_id':'P1',
                                            'relation_type':'used_to_make','material_grade':'OTHER'}])
        self.assertEqual(self.db.counts()['relations'], 0)

    def test_fact_records_cannot_reuse_demo_objects(self):
        run_demo(self.db.path)
        with self.assertRaisesRegex(DataError, 'demo entity'):
            self.fixture.load('prices', [self.fixture.price(material_id='MATERIAL_M1', grade='DEMO_GRADE')])

    def test_invalid_decimal_format_is_rejected(self):
        for value in ['1_000', '１０', '1,000']:
            with self.subTest(value=value), self.assertRaises(DataError):
                _number(value, 'value')
        self.assertEqual(_number('1.25e2', 'value'), '125')

    def test_bad_date_types_raise_data_error(self):
        for value in [1, False, [], {}]:
            with self.subTest(value=value), self.assertRaises(DataError):
                iso_date(value)

    def test_legacy_query_rejects_invalid_types(self):
        query = EvidenceQuery(self.db)
        for arguments in [{'query':None}, {'limit':True}, {'limit':1.5},
                          {'document_id':[]}, {'as_of':1}]:
            with self.subTest(arguments=arguments), self.assertRaises(DataError):
                query.search(**arguments)

    def test_duplicate_import_checks_original_snapshot(self):
        source = self.db.document('SOURCE')
        original = Path(source['file_path']).resolve()
        self.assertTrue(original.is_relative_to(self.fixture.root.resolve()))
        original.unlink()
        with self.assertRaisesRegex(DataError, 'original'):
            self.fixture.importer.import_pdf(self.fixture.root / 'fixture.pdf', document_id='SOURCE',
                                             published_on='2026-09-01')

    def test_query_detects_modified_source_copy(self):
        self.fixture.load('prices', [self.fixture.price()])
        found = self.fixture.prices()['data']['records'][0]
        original = Path(found['source']['file_path']).resolve()
        self.assertTrue(original.is_relative_to(self.fixture.root.resolve()))
        original.write_bytes(b'modified snapshot')
        result = self.fixture.prices()
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error']['code'], 'SOURCE_INTEGRITY_ERROR')

    def test_demo_modules_run_with_python_m(self):
        for module in ['examples.run_demo', 'examples.run_query_demo']:
            with self.subTest(module=module):
                database = self.fixture.root / (module.split('.')[-1] + '.sqlite')
                result = subprocess.run([sys.executable, '-X', 'utf8', '-m', module, '--db', str(database)],
                                        cwd=fixtures.ROOT, capture_output=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data['counts']['documents'], 7)

    def test_demo_output_cannot_overwrite_database(self):
        before = self.db.counts()
        result = subprocess.run([sys.executable, str(fixtures.ROOT / 'examples/run_demo.py'),
                                 '--db', str(self.db.path), '--output', str(self.db.path)],
                                capture_output=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.db.counts(), before)


if __name__ == '__main__':
    unittest.main()

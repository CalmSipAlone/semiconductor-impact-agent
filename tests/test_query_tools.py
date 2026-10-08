"""Synthetic fact flags exercise filters; fixtures are not real market data."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'examples')]
from build_demo_pdf import write_pdf
from run_demo import run_demo
from run_query_demo import run_query_demo
from semiconductor_agent.ingest import Importer
from semiconductor_agent.storage import Database
from semiconductor_agent.tools import QueryTools


class QueryToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = Database(self.root / 'tools.sqlite')
        self.importer = Importer(self.db)
        self.tools = QueryTools(self.db)
        self.sequence = 0
        pdf = write_pdf(self.root / 'fixture.pdf', [['Synthetic test fixture, not market evidence.']])
        self.importer.import_pdf(pdf, document_id='SOURCE', published_on='2026-09-01')
        self.load('entities', [
            {'entity_id':'M1','entity_type':'material','name':'Resin','grade':'G'},
            {'entity_id':'P1','entity_type':'product','name':'Photoresist','grade':'G'},
            {'entity_id':'P2','entity_type':'product','name':'Chip','grade':'G'},
            {'entity_id':'C1','entity_type':'company','name':'Company','grade':''},
        ])
        self.load('companies', [{'company_id':'C1','company_name':'Company','industry_stage':'test'}])

    def load(self, table, rows, *, published_on='2026-10-01', data_kind='fact'):
        self.sequence += 1
        common = {'source_document_id':'SOURCE','source_page':'1','verification_status':'verified'}
        rows = [{**common, **row} for row in rows]
        fields = list(dict.fromkeys(key for row in rows for key in row))
        path = self.root / f'{table}-{self.sequence}.csv'
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return self.importer.import_csv(path, table=table, published_on=published_on, data_kind=data_kind)

    def price(self, **overrides):
        return {'material_id':'M1','grade':'G','date':'2026-10-01','price':'100','unit':'kg',
                'currency':'CNY','price_basis':'purchase','value_type':'fact', **overrides}

    def prices(self, **overrides):
        return self.tools.call('query_prices', **{'material_id':'M1','grade':'G','unit':'kg',
                               'currency':'CNY','price_basis':'purchase', **overrides})

    def relations(self):
        self.load('relations', [
            {'relation_id':'R1','upstream_id':'M1','downstream_id':'P1','relation_type':'used_to_make'},
            {'relation_id':'R2','upstream_id':'P1','downstream_id':'P2','relation_type':'used_in'},
            {'relation_id':'R3','upstream_id':'P2','downstream_id':'M1','relation_type':'test_cycle'},
            {'relation_id':'R4','upstream_id':'C1','downstream_id':'P1','relation_type':'produces'},
        ])

    def test_registry_and_uniform_errors(self):
        self.assertEqual(set(self.tools.registry()), set(QueryTools.NAMES))
        for result in [self.tools.call('missing'), self.tools.call('query_prices'),
                       self.tools.call('query_relations', entity_id='M1', unexpected=True),
                       self.prices(value_type=[]),
                       self.tools.call('query_relations', entity_id='M1', direction=[]),
                       self.prices(limit=True), self.prices(include_demo='yes')]:
            self.assertEqual(set(result), {'status','data','evidence_ids','warnings','error'})
            self.assertEqual(result['status'], 'error')
            self.assertFalse(result['error']['retryable'])

    def test_unknown_and_wrong_entity_types(self):
        self.assertEqual(self.prices(material_id='unknown')['error']['code'], 'UNKNOWN_ENTITY')
        self.assertEqual(self.prices(material_id='C1')['error']['code'], 'INVALID_INPUT')

    def test_path_depth_cycles_and_direction(self):
        self.relations()
        result = self.tools.registry()['query_relations'](entity_id='M1', depth=4)
        self.assertEqual([p['entity_ids'] for p in result['data']['paths']], [['M1','P1'], ['M1','P1','P2']])
        self.assertTrue(any('Cyclic' in w for w in result['warnings']))
        for path in result['data']['paths']:
            self.assertEqual(len(path['entity_ids']), len(set(path['entity_ids'])))
        upstream = self.tools.call('query_relations', entity_id='P1', direction='upstream', depth=1)
        self.assertEqual({p['entity_ids'][-1] for p in upstream['data']['paths']}, {'M1','C1'})
        filtered = self.tools.call('query_relations', entity_id='P1', direction='upstream', relation_type='produces')
        self.assertEqual(filtered['data']['paths'][0]['entity_ids'], ['P1','C1'])
        both = self.tools.call('query_relations', entity_id='M1', direction='both', depth=1)
        self.assertEqual({p['entity_ids'][-1] for p in both['data']['paths']}, {'P1','P2'})

    def test_path_limit_and_invalid_depth(self):
        self.relations()
        result = self.tools.call('query_relations', entity_id='M1', limit=1, depth=3)
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['data']['truncated'])
        self.assertEqual(result['data']['count'], 1)
        self.assertEqual(self.tools.call('query_relations', entity_id='M1', depth=5)['status'], 'error')

    def test_relation_validity_and_pending_endpoint(self):
        self.load('relations', [{'relation_id':'R1','upstream_id':'M1','downstream_id':'P1',
                                'relation_type':'used_to_make','valid_from':'2026-10-01','valid_to':'2026-10-05'}])
        self.assertEqual(self.tools.call('query_relations', entity_id='M1', as_of='2026-10-08')['data']['count'], 0)
        with self.db.connect() as conn:
            conn.execute("UPDATE entities SET verification_status='pending' WHERE entity_id='P1'")
        self.assertEqual(self.tools.call('query_relations', entity_id='M1')['data']['count'], 0)
        self.assertEqual(self.tools.call('query_relations', entity_id='M1', include_pending=True)['data']['count'], 1)

    def test_prices_exact_scope_and_provenance(self):
        self.load('prices', [self.price(), self.price(date='2026-10-08', price='110')])
        result = self.prices(start_date='2026-10-08', end_date='2026-10-08')
        self.assertEqual(result['status'], 'ok')
        record = result['data']['records'][0]
        self.assertEqual(record['price'], '110')
        self.assertEqual(record['source']['csv_row'], 3)
        self.assertEqual(record['source']['supporting_document']['pdf_page'], 1)
        self.assertTrue(Path(record['source']['file_path']).is_file())
        self.assertTrue(record['source']['supporting_document']['evidence_id'] in result['evidence_ids'])
        for wrong in [{'grade':'OTHER'}, {'unit':'tonne'}, {'currency':'USD'}, {'price_basis':'sale'}]:
            self.assertEqual(self.prices(**wrong)['error']['code'], 'NO_MATCHING_PRICE')

    def test_price_observation_and_publication_dates(self):
        self.load('prices', [self.price(date='2026-10-10')])
        self.assertEqual(self.prices(as_of='2026-10-08')['data']['count'], 0)
        self.load('prices', [self.price(date='2026-10-02')], published_on='2026-10-09')
        self.assertEqual(self.prices(as_of='2026-10-08')['data']['count'], 0)
        self.assertEqual(self.prices(as_of='2026-10-10')['data']['count'], 2)
        self.assertEqual(self.prices(start_date='2026-10-09', end_date='2026-10-01')['status'], 'error')

    def test_supporting_pdf_publication_is_checked(self):
        later = write_pdf(self.root / 'later.pdf', [['Future supporting source']])
        self.importer.import_pdf(later, document_id='LATER', published_on='2026-10-09')
        self.load('prices', [self.price(source_document_id='LATER')])
        self.assertEqual(self.prices(as_of='2026-10-08')['data']['count'], 0)

    def test_missing_and_unknown_entity_publication_dates(self):
        self.assertEqual(self.prices()['error']['code'], 'NO_MATCHING_PRICE')
        self.load('prices', [self.price()], published_on=None)
        self.assertEqual(self.prices(as_of='2026-10-08')['data']['count'], 0)
        self.assertTrue(self.prices()['warnings'])
        with self.db.connect() as conn:
            conn.execute("UPDATE documents SET published_on='2026-10-10' WHERE document_id IN (SELECT document_id FROM evidence_chunks WHERE evidence_id=(SELECT evidence_id FROM entities WHERE entity_id='M1'))")
        self.assertEqual(self.prices(as_of='2026-10-08')['error']['code'], 'NO_ELIGIBLE_ENTITY')

    def test_conflicting_prices_and_equivalent_decimals(self):
        self.load('prices', [self.price(), self.price(price='100.0')])
        self.assertEqual(self.prices()['data']['conflicts'], [])
        self.load('prices', [self.price(price='115')])
        result = self.prices()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['data']['conflicts']), 1)
        self.assertEqual(result['data']['count'], 3)

    def test_price_limit_and_assumption_types(self):
        self.load('prices', [self.price(), self.price(date='2026-10-02')])
        limited = self.prices(limit=1)
        self.assertTrue(limited['data']['truncated'])
        self.load('prices', [self.price(value_type='scenario', assumption_note='synthetic', price='120')])
        self.assertEqual(self.prices()['data']['count'], 2)
        scenario = self.prices(value_type='scenario')
        self.assertEqual(scenario['data']['count'], 1)
        self.assertTrue(scenario['warnings'])
        self.assertEqual(self.prices(value_type='all')['status'], 'partial')

    def test_metrics_and_parameters_scope(self):
        self.load('metrics', [{'metric_id':'MET1','company_id':'C1','metric_name':'revenue','period':'2026Q3',
                               'value':'100000','unit':'元','currency':'CNY'}])
        self.load('parameters', [{'parameter_id':'PAR1','company_id':'C1','product_id':'P1',
                                  'parameter_name':'raw_material_cost_share','value':'0.3','unit':'ratio',
                                  'period':'2026Q3','value_type':'fact'}])
        metrics = {'company_id':'C1','metric_name':'revenue','period':'2026Q3','unit':'元','currency':'CNY'}
        self.assertEqual(self.tools.call('query_metrics', **metrics)['data']['records'][0]['value'], '100000')
        self.assertEqual(self.tools.call('query_metrics', **{**metrics, 'period':'2026Q2'})['error']['code'], 'NO_MATCHING_METRIC')
        parameters = self.tools.call('query_parameters', company_id='C1', product_id='P1', period='2026Q3')
        self.assertEqual(parameters['data']['records'][0]['value'], '0.3')
        self.assertEqual(len(parameters['data']['scope_entities']), 2)
        self.assertEqual(self.tools.call('query_parameters', company_id='C1', period='2026Q3', parameter_name='missing')['error']['code'], 'MISSING_PARAMETER')
        self.assertEqual(self.tools.call('query_parameters', period='2026Q3')['status'], 'error')

    def test_parameter_unrequested_product_is_still_filtered(self):
        self.load('parameters', [{'parameter_id':'PAR1','company_id':'C1','product_id':'P1',
                                  'parameter_name':'test','value':'0.3','unit':'ratio','period':'Q3','value_type':'fact'}])
        with self.db.connect() as conn:
            conn.execute("UPDATE entities SET verification_status='pending' WHERE entity_id='P1'")
        self.assertEqual(self.tools.call('query_parameters', company_id='C1', period='Q3')['data']['count'], 0)
        included = self.tools.call('query_parameters', company_id='C1', period='Q3', include_pending=True)
        self.assertEqual(included['data']['count'], 1)
        self.assertTrue(any('pending' in warning for warning in included['warnings']))
        self.assertEqual({e['entity_id'] for e in included['data']['scope_entities']}, {'C1','P1'})

    def test_default_demo_filter_and_explicit_override(self):
        demo = Database(self.root / 'demo.sqlite')
        run_demo(demo.path)
        tools = QueryTools(demo)
        self.assertEqual(tools.call('query_relations', entity_id='MATERIAL_M1')['error']['code'], 'NO_ELIGIBLE_ENTITY')
        result = tools.call('query_relations', entity_id='MATERIAL_M1', include_demo=True, include_pending=True)
        self.assertEqual(result['data']['count'], 1)
        self.assertTrue(any('fictional' in w for w in result['warnings']))

    def test_pending_numeric_rows_default_exclusion(self):
        self.load('prices', [self.price(verification_status='pending')])
        self.assertEqual(self.prices()['data']['count'], 0)
        self.assertEqual(self.prices(include_pending=True)['data']['count'], 1)

    def test_unified_evidence_search_literal_input_and_limit(self):
        self.load('prices', [self.price()])
        found = self.tools.call('search_evidence', query='material_id: M1')
        self.assertEqual(found['status'], 'ok')
        self.assertEqual(found['data']['count'], 1)
        for query in ['%', "' OR 1=1 --"]:
            self.assertEqual(self.tools.call('search_evidence', query=query)['data']['count'], 0)
        limited = self.tools.call('search_evidence', limit=1)
        self.assertEqual(limited['status'], 'partial')
        self.assertTrue(limited['data']['truncated'])

    def test_cli_new_tools_keep_old_commands(self):
        self.relations()
        command = [sys.executable, str(ROOT / 'cli.py'), '--db', str(self.db.path)]
        found = subprocess.run([*command, 'query-relations', 'M1'], capture_output=True, encoding='utf-8')
        self.assertEqual(found.returncode, 0)
        self.assertTrue(json.loads(found.stdout)['data']['paths'])
        missing = subprocess.run([*command, 'query-relations', 'unknown'], capture_output=True, encoding='utf-8')
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(json.loads(missing.stdout)['error']['code'], 'UNKNOWN_ENTITY')
        old = subprocess.run([*command, 'stats'], capture_output=True, encoding='utf-8')
        self.assertEqual(old.returncode, 0)
        self.assertEqual(json.loads(old.stdout)['relations'], 4)

    def test_tools_do_not_mutate_data(self):
        self.relations()
        self.load('prices', [self.price()])
        before = self.db.counts()
        self.tools.call('query_relations', entity_id='M1', depth=4)
        self.prices()
        self.tools.call('query_parameters', company_id='C1', period='Q3')
        self.assertEqual(self.db.counts(), before)

    def test_complete_query_demo_has_all_business_records(self):
        result = run_query_demo(self.root / 'full-demo.sqlite')
        expected = {'relations':1,'prices':2,'metrics':1,'parameters':1,'evidence':4}
        for tool, count in expected.items():
            self.assertEqual(result['queries'][tool]['data']['count'], count)
            self.assertEqual(result['queries'][tool]['status'], 'ok')
        self.assertEqual(result['queries']['default_filter']['data']['records'], [])
        self.assertEqual(result['queries']['missing_price']['error']['code'], 'NO_MATCHING_PRICE')

    def test_neighbor_cap_marks_incomplete_graph(self):
        self.relations()
        with patch.object(self.tools, 'MAX_NEIGHBORS', 1):
            result = self.tools.call('query_relations', entity_id='M1', direction='both', depth=1)
        self.assertTrue(result['data']['truncated'])
        self.assertEqual(result['status'], 'partial')

    def test_timeout_has_structured_retryable_error(self):
        self.relations()
        times = iter([0, 0])
        with patch('semiconductor_agent.tools.time.monotonic', side_effect=lambda: next(times, 6)):
            result = self.tools.call('query_relations', entity_id='M1', depth=4)
        self.assertEqual(result['error']['code'], 'TOOL_TIMEOUT')
        self.assertTrue(result['error']['retryable'])


if __name__ == '__main__':
    unittest.main()

"""Bounded, read-only business tools for a future agent; no financial inference."""
import inspect
import json
import sqlite3
import time
from collections import deque
from decimal import Decimal
from functools import partial

from .errors import DataError, SourceIntegrityError
from .ingest import _currency, iso_date


class ToolError(DataError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def response(data=None, *, status='ok', warnings=(), code=None, message=None, retryable=False):
    evidence_ids = set()

    def collect(value):
        if isinstance(value, dict):
            if value.get('evidence_id'):
                evidence_ids.add(value['evidence_id'])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(data)
    return {'status': status, 'data': data or {}, 'evidence_ids': sorted(evidence_ids),
            'warnings': list(dict.fromkeys(warnings)),
            'error': {'code': code, 'message': message, 'retryable': retryable} if code else None}


def text(value, field, *, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise ToolError('INVALID_INPUT', f'{field} must be a nonempty string of at most 1000 characters')
    return value.strip()


class QueryTools:
    NAMES = ('search_evidence', 'query_relations', 'query_prices', 'query_metrics', 'query_parameters')
    MAX_NEIGHBORS = 500

    def __init__(self, database):
        self.db = database

    def registry(self):
        """Ordinary synchronous Python callables, independent of any LLM framework."""
        return {name: partial(self.call, name) for name in self.NAMES}

    def call(self, name, **arguments):
        if name not in self.NAMES:
            return response(status='error', code='UNKNOWN_TOOL', message=f'Unknown tool: {name}')
        method = getattr(self, '_' + name)
        try:
            inspect.signature(method).bind(None, **arguments)
        except TypeError as exc:
            return response(status='error', code='INVALID_INPUT', message=str(exc))
        try:
            self.db.initialize()
            with self.db.connect() as conn:
                # One read snapshot for the complete tool response, including its sources.
                conn.execute('BEGIN')
                deadline = time.monotonic() + 5
                conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                try:
                    result = method(conn, **arguments)
                    self.db.verify_sources(result['data'])
                    if time.monotonic() > deadline:
                        raise ToolError('TOOL_TIMEOUT', 'Query exceeded five seconds')
                    return result
                finally:
                    conn.set_progress_handler(None, 0)
        except ToolError as exc:
            return response(status='error', code=exc.code, message=str(exc), retryable=exc.code == 'TOOL_TIMEOUT')
        except SourceIntegrityError as exc:
            return response(status='error', code='SOURCE_INTEGRITY_ERROR', message=str(exc))
        except DataError as exc:
            return response(status='error', code='INVALID_INPUT', message=str(exc))
        except sqlite3.OperationalError as exc:
            timeout = 'interrupted' in str(exc).lower()
            return response(status='error', code='TOOL_TIMEOUT' if timeout else 'DATABASE_ERROR',
                            message=str(exc), retryable=timeout or 'locked' in str(exc).lower())
        except (sqlite3.Error, OSError) as exc:
            return response(status='error', code='DATABASE_ERROR', message=str(exc))

    def _policy(self, as_of, limit, include_pending, include_demo):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ToolError('INVALID_INPUT', 'limit must be an integer from 1 to 100')
        if type(include_pending) is not bool or type(include_demo) is not bool:
            raise ToolError('INVALID_INPUT', 'include_pending/include_demo must be booleans')
        if as_of is not None:
            as_of = iso_date(text(as_of, 'as_of'), 'as_of')
        return as_of

    def _select(self, conn, table, conditions=(), arguments=(), *, order, limit):
        allowed = {'entities', 'relations', 'prices', 'metrics', 'parameters', 'evidence_chunks'}
        if table not in allowed:
            raise ValueError('Internal table name is not allowed')
        sql = f'''SELECT t.*, e.document_id AS _document_id, e.locator AS _locator,
                    e.pdf_page AS _pdf_page, e.csv_row AS _csv_row,
                    d.original_name AS _original_name, d.stored_path AS _stored_path,
                    d.source_url AS _source_url, d.published_on AS _published_on,
                    d.data_kind AS _data_kind, d.sha256 AS _sha256,
                    s.document_id AS _support_id, e.supporting_pdf_page AS _support_page,
                    s.original_name AS _support_name, s.stored_path AS _support_path,
                    s.source_url AS _support_url, s.published_on AS _support_date,
                    s.data_kind AS _support_kind, s.sha256 AS _support_hash,
                    se.evidence_id AS _support_evidence
                 FROM {table} t JOIN evidence_chunks e ON e.evidence_id=t.evidence_id
                 JOIN documents d ON d.document_id=e.document_id
                 LEFT JOIN documents s ON s.document_id=e.supporting_document_id
                 LEFT JOIN evidence_chunks se ON se.document_id=s.document_id
                        AND se.pdf_page=e.supporting_pdf_page'''
        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)
        sql += ' ORDER BY ' + order + ' LIMIT ?'
        result = []
        for row in conn.execute(sql, [*arguments, limit]):
            item = dict(row)
            source = {'evidence_id': item['evidence_id'], 'document_id': item['_document_id'],
                      'locator': item['_locator'], 'pdf_page': item['_pdf_page'], 'csv_row': item['_csv_row'],
                      'original_name': item['_original_name'], 'source_url': item['_source_url'],
                      'published_on': item['_published_on'], 'data_kind': item['_data_kind'],
                      'sha256': item['_sha256'],
                      'file_path': str(self.db.path.parent / item['_stored_path'])}
            if item['_support_id']:
                source['supporting_document'] = {
                    'document_id': item['_support_id'], 'pdf_page': item['_support_page'],
                    'evidence_id': item['_support_evidence'], 'original_name': item['_support_name'],
                    'source_url': item['_support_url'], 'published_on': item['_support_date'],
                    'data_kind': item['_support_kind'], 'sha256': item['_support_hash'],
                    'file_path': str(self.db.path.parent / item['_support_path'])}
            item = {k: v for k, v in item.items() if not k.startswith('_')}
            item['source'] = source
            if 'aliases_json' in item:
                item['aliases'] = json.loads(item.pop('aliases_json'))
            result.append(item)
        return result

    def _filters(self, as_of, include_pending, include_demo, *, has_status=True):
        conditions, args = [], []
        if has_status and not include_pending:
            conditions.append("t.verification_status='verified'")
        if not include_demo:
            conditions += ["d.data_kind='fact'", "(s.document_id IS NULL OR s.data_kind='fact')"]
        if as_of:
            conditions += ['d.published_on IS NOT NULL', 'd.published_on <= ?',
                           '(s.document_id IS NULL OR (s.published_on IS NOT NULL AND s.published_on <= ?))']
            args += [as_of, as_of]
        return conditions, args

    def _entity(self, conn, entity_id, expected=None):
        entity_id = text(entity_id, 'entity_id')
        rows = self._select(conn, 'entities', ['t.entity_id=?'], [entity_id], order='t.entity_id', limit=1)
        if not rows:
            raise ToolError('UNKNOWN_ENTITY', f'Unknown entity_id: {entity_id}')
        entity = rows[0]
        if expected and entity['entity_type'] != expected:
            raise ToolError('INVALID_INPUT', f'{entity_id} must be a {expected}')
        return entity

    def _linked_filters(self, columns, as_of, include_pending, include_demo):
        """Filter every referenced scope object, even if not supplied as an input."""
        conditions, args = [], []
        for column in columns:
            if column not in {'company_id', 'product_id'}:
                raise ValueError('Internal scope column is not allowed')
            clauses = [f'q.entity_id=t.{column}']
            if not include_pending:
                clauses.append("q.verification_status='verified'")
            if not include_demo:
                clauses += ["qd.data_kind='fact'", "(qs.document_id IS NULL OR qs.data_kind='fact')"]
            if as_of:
                clauses += ['qd.published_on IS NOT NULL', 'qd.published_on <= ?',
                            '(qs.document_id IS NULL OR (qs.published_on IS NOT NULL AND qs.published_on <= ?))']
                args += [as_of, as_of]
            conditions.append(f'''(t.{column} IS NULL OR EXISTS (
                SELECT 1 FROM entities q JOIN evidence_chunks qe ON qe.evidence_id=q.evidence_id
                JOIN documents qd ON qd.document_id=qe.document_id
                LEFT JOIN documents qs ON qs.document_id=qe.supporting_document_id
                WHERE {' AND '.join(clauses)}))''')
        return conditions, args

    def _visible(self, entity, as_of, include_pending, include_demo):
        if not include_pending and entity['verification_status'] != 'verified':
            return False
        for source in [entity['source'], entity['source'].get('supporting_document')]:
            if source is None:
                continue
            if not include_demo and source['data_kind'] == 'demo':
                return False
            if as_of and (not source['published_on'] or source['published_on'] > as_of):
                return False
        return True

    def _warnings(self, items, as_of):
        warnings = []
        for item in items:
            if item.get('verification_status') == 'pending':
                warnings.append('Returned records include pending verification; do not treat them as verified facts.')
            if item.get('value_type') in {'estimate', 'scenario'}:
                warnings.append('Returned numerical inputs include estimates/scenarios; preserve their assumption notes.')
            for source in [item.get('source'), (item.get('source') or {}).get('supporting_document')]:
                if source and source['data_kind'] == 'demo':
                    warnings.append('Returned sources include fictional demo data.')
                if source and not source['published_on']:
                    warnings.append('A returned source has an unknown publication date; historical availability is unverified.')
        if as_of:
            warnings.append('Sources with unknown or later publication dates are excluded by as_of.')
        return warnings

    def _missing_entity(self, entity):
        # Do not expose excluded source text or count its evidence as used.
        return response({'entity_id': entity['entity_id'], 'records': [], 'count': 0,
                         'truncated': False, 'missing_fields': ['eligible_entity']},
                        status='partial', code='NO_ELIGIBLE_ENTITY',
                        message='Entity is excluded by verification, demo or publication filters.')

    def _numeric_finish(self, records, entity, scope, *, limit, as_of, code, identity):
        truncated = len(records) > limit
        records = records[:limit]
        warnings = self._warnings([entity, *records], as_of)
        data = {'entity': entity, 'filters': scope, 'records': records, 'count': len(records),
                'truncated': truncated, 'missing_fields': [], 'conflicts': []}
        if not records:
            data['missing_fields'] = ['matching_records']
            return response(data, status='partial', warnings=warnings, code=code,
                            message='No records match the requested scope; no fallback or conversion was applied.')
        groups = {}
        for record in records:
            key = tuple(record[field] for field in identity)
            groups.setdefault(key, []).append(record)
        for key, group in groups.items():
            value_field = 'price' if 'price' in group[0] else 'value'
            if len({Decimal(record[value_field]) for record in group}) > 1:
                data['conflicts'].append({'scope': dict(zip(identity, key)),
                                         'evidence_ids': [record['evidence_id'] for record in group],
                                         'values': [record[value_field] for record in group]})
        if data['conflicts']:
            warnings.append('Conflicting values share the requested scope; no authoritative value was selected.')
        if len({record['value_type'] for record in records}) > 1:
            warnings.append('Mixed fact/estimate/scenario records must not be merged into one factual series.')
        if truncated:
            warnings.append('Record limit reached; results and conflict checks cover only the returned subset.')
        partial_result = truncated or bool(data['conflicts']) or len({r['value_type'] for r in records}) > 1
        return response(data, status='partial' if partial_result else 'ok', warnings=warnings)

    def _value_filter(self, value_type, conditions, args):
        if not isinstance(value_type, str) or value_type not in {'fact', 'estimate', 'scenario', 'all'}:
            raise ToolError('INVALID_INPUT', 'value_type must be fact, estimate, scenario or all')
        if value_type != 'all':
            conditions.append('t.value_type=?')
            args.append(value_type)

    def _query_prices(self, conn, *, material_id, grade, unit, currency, price_basis,
                      start_date=None, end_date=None, as_of=None, limit=20,
                      include_pending=False, include_demo=False, value_type='fact'):
        as_of = self._policy(as_of, limit, include_pending, include_demo)
        scope = {k: text(v, k) for k, v in {'grade': grade, 'unit': unit, 'currency': currency,
                                          'price_basis': price_basis}.items()}
        _currency(scope['currency'])
        start = iso_date(text(start_date, 'start_date', optional=True), 'start_date')
        end = iso_date(text(end_date, 'end_date', optional=True), 'end_date')
        if start and end and start > end:
            raise ToolError('INVALID_INPUT', 'start_date must not be later than end_date')
        conditions, args = self._filters(as_of, include_pending, include_demo)
        self._value_filter(value_type, conditions, args)
        entity = self._entity(conn, material_id, 'material')
        if not self._visible(entity, as_of, include_pending, include_demo):
            return self._missing_entity(entity)
        conditions.append('t.material_id=?')
        args.append(entity['entity_id'])
        for key, value in scope.items():
            conditions.append(f't.{key}=?')
            args.append(value)
        for operator, value in [('>=', start), ('<=', end), ('<=', as_of)]:
            if value:
                conditions.append(f't.date {operator} ?')
                args.append(value)
        scope.update(start_date=start, end_date=end, as_of=as_of, value_type=value_type,
                     include_pending=include_pending, include_demo=include_demo)
        records = self._select(conn, 'prices', conditions, args, order='t.date, t.price_id', limit=limit + 1)
        return self._numeric_finish(records, entity, scope, limit=limit, as_of=as_of,
                                    code='NO_MATCHING_PRICE',
                                    identity=('material_id', 'grade', 'date', 'unit', 'currency', 'price_basis', 'value_type'))

    def _query_metrics(self, conn, *, company_id, metric_name, period, unit, currency,
                       as_of=None, limit=20, include_pending=False, include_demo=False, value_type='fact'):
        as_of = self._policy(as_of, limit, include_pending, include_demo)
        scope = {k: text(v, k) for k, v in {'metric_name': metric_name, 'period': period,
                                          'unit': unit, 'currency': currency}.items()}
        _currency(scope['currency'])
        conditions, args = self._filters(as_of, include_pending, include_demo)
        self._value_filter(value_type, conditions, args)
        entity = self._entity(conn, company_id, 'company')
        if not self._visible(entity, as_of, include_pending, include_demo):
            return self._missing_entity(entity)
        conditions.append('t.company_id=?')
        args.append(entity['entity_id'])
        for key, value in scope.items():
            conditions.append(f't.{key}=?')
            args.append(value)
        scope.update(as_of=as_of, value_type=value_type, include_pending=include_pending, include_demo=include_demo)
        records = self._select(conn, 'metrics', conditions, args, order='t.metric_id', limit=limit + 1)
        return self._numeric_finish(records, entity, scope, limit=limit, as_of=as_of,
                                    code='NO_MATCHING_METRIC',
                                    identity=('company_id', 'metric_name', 'period', 'unit', 'currency', 'value_type'))

    def _query_parameters(self, conn, *, period, company_id=None, product_id=None, parameter_name=None,
                          unit=None, as_of=None, limit=20, include_pending=False, include_demo=False, value_type='fact'):
        as_of = self._policy(as_of, limit, include_pending, include_demo)
        if not company_id and not product_id:
            raise ToolError('INVALID_INPUT', 'Supply company_id or product_id to scope the parameters')
        scope = {'period': text(period, 'period'), 'company_id': company_id, 'product_id': product_id,
                 'parameter_name': text(parameter_name, 'parameter_name', optional=True),
                 'unit': text(unit, 'unit', optional=True)}
        conditions, args = self._filters(as_of, include_pending, include_demo)
        self._value_filter(value_type, conditions, args)
        entities = []
        for key, expected in [('company_id', 'company'), ('product_id', 'product')]:
            if scope[key] is not None:
                scope[key] = text(scope[key], key)
                entity = self._entity(conn, scope[key], expected)
                if not self._visible(entity, as_of, include_pending, include_demo):
                    return self._missing_entity(entity)
                entities.append(entity)
        linked_conditions, linked_args = self._linked_filters(('company_id', 'product_id'), as_of, include_pending, include_demo)
        conditions += linked_conditions
        args += linked_args
        for key, value in scope.items():
            if value is not None:
                conditions.append(f't.{key}=?')
                args.append(value)
        scope.update(as_of=as_of, value_type=value_type, include_pending=include_pending, include_demo=include_demo)
        records = self._select(conn, 'parameters', conditions, args, order='t.parameter_name, t.parameter_id', limit=limit + 1)
        result = self._numeric_finish(records, entities[0], scope, limit=limit, as_of=as_of,
                                      code='MISSING_PARAMETER',
                                      identity=('company_id', 'product_id', 'parameter_name', 'period', 'unit', 'value_type'))
        referenced = {entity['entity_id']: entity for entity in entities}
        for record in result['data']['records']:
            for column, expected in [('company_id', 'company'), ('product_id', 'product')]:
                if record[column] and record[column] not in referenced:
                    referenced[record[column]] = self._entity(conn, record[column], expected)
        result['data']['scope_entities'] = list(referenced.values())
        # Preserve provenance and verification warnings for every referenced scope object.
        warnings = result['warnings'] + self._warnings(list(referenced.values()), as_of)
        return response(result['data'], status=result['status'], warnings=warnings,
                        **({'code': result['error']['code'], 'message': result['error']['message']} if result['error'] else {}))

    def _query_relations(self, conn, *, entity_id, direction='downstream', relation_type=None, depth=2,
                         as_of=None, limit=30, include_pending=False, include_demo=False):
        as_of = self._policy(as_of, limit, include_pending, include_demo)
        if not isinstance(direction, str) or direction not in {'upstream', 'downstream', 'both'}:
            raise ToolError('INVALID_INPUT', 'direction must be upstream, downstream or both')
        if type(depth) is not int or not 1 <= depth <= 4:
            raise ToolError('INVALID_INPUT', 'depth must be an integer from 1 to 4')
        relation_type = text(relation_type, 'relation_type', optional=True)
        root = self._entity(conn, entity_id)
        if not self._visible(root, as_of, include_pending, include_demo):
            return self._missing_entity(root)
        entity_cache, neighbor_cache = {root['entity_id']: root}, {}
        queue = deque([([root['entity_id']], [])])
        paths, returned_relations = [], {}
        truncated, cycle_skipped = False, False
        started = time.monotonic()
        while queue:
            if time.monotonic() - started > 5:
                raise ToolError('TOOL_TIMEOUT', 'Graph traversal exceeded five seconds')
            nodes, edges = queue.popleft()
            if len(edges) >= depth:
                continue
            current = nodes[-1]
            if current not in neighbor_cache:
                conditions, args = self._filters(as_of, include_pending, include_demo)
                clause = {'downstream': 't.upstream_id=?', 'upstream': 't.downstream_id=?',
                          'both': '(t.upstream_id=? OR t.downstream_id=?)'}[direction]
                conditions.append(clause)
                args += [current, current] if direction == 'both' else [current]
                if relation_type:
                    conditions.append('t.relation_type=?')
                    args.append(relation_type)
                if as_of:
                    conditions += ['(t.valid_from IS NULL OR t.valid_from <= ?)',
                                   '(t.valid_to IS NULL OR t.valid_to >= ?)']
                    args += [as_of, as_of]
                neighbors = self._select(conn, 'relations', conditions, args, order='t.relation_id',
                                         limit=self.MAX_NEIGHBORS + 1)
                if len(neighbors) > self.MAX_NEIGHBORS:
                    truncated = True
                neighbor_cache[current] = neighbors[:self.MAX_NEIGHBORS]
            for edge in neighbor_cache[current]:
                target = edge['downstream_id'] if edge['upstream_id'] == current else edge['upstream_id']
                if target in nodes:
                    cycle_skipped = True
                    continue
                if target not in entity_cache:
                    entity_cache[target] = self._entity(conn, target)
                if not self._visible(entity_cache[target], as_of, include_pending, include_demo):
                    continue
                if len(paths) >= limit:
                    truncated = True
                    queue.clear()
                    break
                next_nodes, next_edges = [*nodes, target], [*edges, edge['relation_id']]
                paths.append({'entity_ids': next_nodes, 'relation_ids': next_edges,
                              'hops': len(next_edges), 'traversal_direction': direction})
                returned_relations[edge['relation_id']] = edge
                queue.append((next_nodes, next_edges))
        ids = {n for path in paths for n in path['entity_ids']} | {root['entity_id']}
        entities = [entity_cache[key] for key in sorted(ids)]
        relations = [returned_relations[key] for key in sorted(returned_relations)]
        warnings = self._warnings([*entities, *relations], as_of)
        warnings.append('Relation paths describe recorded links; they are not causal proof or cost weights.')
        if direction == 'both':
            warnings.append('Both-direction traversal may reverse recorded edges; inspect original upstream/downstream fields.')
        if cycle_skipped:
            warnings.append('Cyclic routes were skipped; paths do not repeat an entity.')
        if truncated:
            warnings.append('Traversal limit reached; the returned graph is incomplete.')
        data = {'root_entity_id': root['entity_id'], 'direction': direction, 'depth': depth,
                'relation_type': relation_type, 'as_of': as_of, 'paths': paths,
                'relations': relations, 'entities': entities, 'count': len(paths), 'truncated': truncated}
        if not paths:
            return response(data, status='partial', warnings=warnings, code='NO_MATCHING_RELATION',
                            message='No eligible relation paths; no unknown links were inferred.')
        return response(data, status='partial' if truncated else 'ok', warnings=warnings)

    def _search_evidence(self, conn, *, query='', document_id=None, as_of=None, limit=10, include_demo=False):
        as_of = self._policy(as_of, limit, False, include_demo)
        if not isinstance(query, str) or len(query) > 1000 or len(query.split()) > 20:
            raise ToolError('INVALID_INPUT', 'query must be a string <=1000 characters with <=20 search terms')
        conditions, args = self._filters(as_of, False, include_demo, has_status=False)
        for term in query.split():
            conditions.append("t.text LIKE ? ESCAPE '\\'")
            escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            args.append('%' + escaped + '%')
        if document_id is not None:
            conditions.append('t.document_id=?')
            args.append(text(document_id, 'document_id'))
        records = self._select(conn, 'evidence_chunks', conditions, args,
                               order='t.document_id, COALESCE(t.pdf_page,t.csv_row)', limit=limit + 1)
        truncated = len(records) > limit
        records = records[:limit]
        warnings = self._warnings(records, as_of)
        warnings.append('Raw evidence search does not certify facts or perform business-record verification.')
        if truncated:
            warnings.append('Evidence limit reached; results are incomplete.')
        data = {'query': query, 'records': records, 'count': len(records), 'truncated': truncated}
        if not records:
            return response(data, status='partial', warnings=warnings, code='NO_MATCHING_EVIDENCE',
                            message='No evidence matched the query and source filters.')
        return response(data, status='partial' if truncated else 'ok', warnings=warnings)

"""Transactional local ingestion. No network access, inference or invented data."""
import csv
import hashlib
import io
import re
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .errors import DataError
from .storage import Database

MAX_BYTES = 25 * 1024 * 1024
COMMON = {'source_document_id', 'source_page', 'verification_status'}
SPECS = {
    'entities': ({'entity_id', 'entity_type', 'name'}, {'grade', 'aliases'}),
    'companies': ({'company_id', 'company_name', 'industry_stage'}, {'security_code'}),
    'relations': ({'relation_id', 'upstream_id', 'downstream_id', 'relation_type'},
                  {'upstream_name', 'downstream_name', 'material_grade', 'valid_from', 'valid_to'}),
    'prices': ({'material_id', 'grade', 'date', 'price', 'unit', 'currency', 'price_basis'},
               {'material_name', 'source_url', 'value_type', 'assumption_note'}),
    'parameters': ({'parameter_id', 'parameter_name', 'value', 'unit', 'period', 'value_type'},
                   {'company_id', 'product_id', 'assumption_note'}),
    'metrics': ({'metric_id', 'company_id', 'metric_name', 'period', 'value', 'unit', 'currency'},
                {'value_type', 'assumption_note'}),
}


def iso_date(value, field='date'):
    if value is None:
        return None
    if not isinstance(value, str):
        raise DataError(f'{field} must use a YYYY-MM-DD string')
    if value == '':
        return None
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError as exc:
        raise DataError(f'{field} must use YYYY-MM-DD: {value}') from exc
    return value


def _id(value, field):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value):
        raise DataError(f'{field} must be an ASCII identifier (1-128 characters)')
    return value


def _number(value, field, nonnegative=False):
    if not isinstance(value, str) or len(value) > 256 or not re.fullmatch(
            r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', value):
        raise DataError(f'{field} must be a finite decimal in ASCII format')
    try:
        result = Decimal(value)
        if not result.is_finite() or len(result.as_tuple().digits) > 28 or abs(result.adjusted()) > 100:
            raise InvalidOperation()
        if nonnegative and result < 0:
            raise InvalidOperation()
    except (InvalidOperation, ValueError) as exc:
        raise DataError(f'{field} must be a finite decimal' + (' >= 0' if nonnegative else '')) from exc
    return str(result)


def _currency(value):
    if not re.fullmatch(r'[A-Z]{3}', value):
        raise DataError('currency must be a three-letter uppercase code, e.g. CNY')
    return value


class Importer:
    def __init__(self, database: Database):
        self.db = database

    def _log_completed(self, operation, result):
        # The transaction has committed. A log I/O failure must not claim that
        # the data import rolled back, or invite a misleading retry.
        try:
            self.db.log({'operation': operation, **result})
        except OSError as exc:
            result.setdefault('warnings', []).append(f'Import committed, but audit log could not be written: {exc}')

    def _read(self, path, extension):
        try:
            path = Path(path).resolve()
        except (TypeError, ValueError) as exc:
            raise DataError('File path must be a valid path string or Path object') from exc
        if not path.is_file() or path.suffix.lower() != extension:
            raise DataError(f'Expected an existing {extension} file: {path}')
        if path.stat().st_size > MAX_BYTES:
            raise DataError('File exceeds the 25 MiB limit')
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            raise DataError('File exceeds the 25 MiB limit')
        if not raw:
            raise DataError('File is empty')
        return path, raw, hashlib.sha256(raw).hexdigest()

    def _duplicate(self, conn, digest, document_id, data_kind, source_url, published_on):
        row = conn.execute('SELECT * FROM documents WHERE sha256=?', (digest,)).fetchone()
        if row is None:
            return None
        self.db.verify_original(row['stored_path'], row['sha256'])
        if document_id and document_id != row['document_id']:
            raise DataError(f'Identical file already registered as {row["document_id"]}; use that ID')
        if data_kind != row['data_kind']:
            raise DataError('Identical content cannot be relabeled between fact and demo')
        for field, value in [('source_url', source_url), ('published_on', published_on)]:
            if value is not None and value != row[field]:
                raise DataError(f'Conflicting {field} for identical file; metadata was not overwritten')
        return {'status': 'duplicate', 'document_id': row['document_id'], 'sha256': digest,
                'message': 'No records added', 'data_kind': row['data_kind']}

    def _register(self, conn, path, raw, digest, kind, document_id, source_url, published_on,
                  data_kind, page_count=None, extraction_status='ready'):
        if not isinstance(data_kind, str) or data_kind not in {'fact', 'demo'}:
            raise DataError('data_kind must be fact or demo')
        document_id = _id('doc_' + digest[:20] if document_id is None else document_id, 'document_id')
        published_on = iso_date(published_on, 'published_on')
        if source_url is not None and (not isinstance(source_url, str) or not source_url.strip()):
            raise DataError('source_url must be a nonempty string or None')
        stored = Path('sources') / (digest + path.suffix.lower())
        destination = self.db.path.parent / stored
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise DataError('Stored original hash mismatch')
        else:
            destination.write_bytes(raw)
        conn.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                     (document_id, digest, kind, path.name, stored.as_posix(), source_url,
                      published_on, data_kind, page_count,
                      extraction_status, datetime.now(timezone.utc).isoformat()))
        return document_id

    def _evidence(self, conn, document_id, text, pdf_page=None, csv_row=None, supporting=None):
        locator = f'pdf:{pdf_page}' if pdf_page is not None else f'csv:{csv_row}'
        evidence_id = 'ev_' + hashlib.sha256(f'{document_id}:{locator}'.encode()).hexdigest()[:24]
        support_id, support_page = supporting or (None, None)
        conn.execute('INSERT INTO evidence_chunks VALUES (?,?,?,?,?,?,?,?)',
                     (evidence_id, document_id, locator, pdf_page, csv_row, text, support_id, support_page))
        return evidence_id

    def import_pdf(self, path, *, document_id=None, source_url=None, published_on=None, data_kind='fact'):
        from pypdf import PdfReader
        path, raw, digest = self._read(path, '.pdf')
        self.db.initialize()
        with self.db.connect() as conn:
            duplicate = self._duplicate(conn, digest, document_id, data_kind, source_url, published_on)
            if duplicate:
                return duplicate
        try:
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise DataError('Encrypted PDF is not supported; supply an authorized readable copy')
            if not reader.pages:
                raise DataError('PDF has no pages')
            pages = [(i, page.extract_text() or '') for i, page in enumerate(reader.pages, 1)]
        except DataError:
            raise
        except Exception as exc:
            raise DataError(f'PDF parsing failed: {type(exc).__name__}: {exc}') from exc
        text_pages = [(i, text.strip()) for i, text in pages if text.strip()]
        warnings = [f'PDF page {i} has no extractable text; OCR/manual review required'
                    for i, text in pages if not text.strip()]
        try:
            with self.db.connect() as conn:
                # Recheck under the write transaction for concurrent import attempts.
                conn.execute('BEGIN IMMEDIATE')
                duplicate = self._duplicate(conn, digest, document_id, data_kind, source_url, published_on)
                if duplicate:
                    return duplicate
                document_id = self._register(conn, path, raw, digest, 'pdf', document_id,
                                             source_url, published_on, data_kind, len(pages),
                                             'ready' if text_pages else 'needs_ocr')
                for page_number, text in text_pages:
                    self._evidence(conn, document_id, text, pdf_page=page_number)
        except sqlite3.IntegrityError as exc:
            raise DataError(f'PDF document registration conflict: {exc}') from exc
        result = {'status': 'imported' if text_pages else 'needs_ocr', 'document_id': document_id,
                  'sha256': digest, 'page_count': len(pages), 'evidence_count': len(text_pages),
                  'data_kind': data_kind, 'warnings': warnings}
        self._log_completed('import_pdf', result)
        return result

    def import_csv(self, path, *, table, document_id=None, source_url=None, published_on=None,
                   data_kind='fact'):
        if not isinstance(table, str) or table not in SPECS:
            raise DataError(f'Unsupported CSV table: {table}')
        path, raw, digest = self._read(path, '.csv')
        try:
            reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
            headers = reader.fieldnames
            required, optional = SPECS[table]
            if not headers or len(set(headers)) != len(headers):
                raise DataError('CSV needs unique column headers')
            missing = required - set(headers)
            unknown = set(headers) - (required | optional | COMMON)
            if missing or unknown:
                raise DataError(f'CSV columns: missing={sorted(missing)}, unknown={sorted(unknown)}')
            rows = []
            for row_number, row in enumerate(reader, 2):
                if None in row or any(v is None for v in row.values()):
                    raise DataError(f'CSV row {row_number}: column count does not match header')
                row = {k: v.strip() for k, v in row.items()}
                empty = sorted(k for k in required if not row[k])
                if empty:
                    raise DataError(f'CSV row {row_number}: required values missing: {empty}')
                rows.append((row_number, row))
            if not rows:
                raise DataError('CSV has a header but no data rows')
        except (UnicodeDecodeError, csv.Error) as exc:
            raise DataError(f'Invalid UTF-8 CSV: {exc}') from exc
        self.db.initialize()
        try:
            with self.db.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                duplicate = self._duplicate(conn, digest, document_id, data_kind, source_url, published_on)
                if duplicate:
                    return duplicate
                document_id = self._register(conn, path, raw, digest, 'csv', document_id,
                                             source_url, published_on, data_kind)
                for row_number, row in rows:
                    try:
                        support = self._support(conn, row, data_kind)
                        text = '\n'.join(f'{key}: {value}' for key, value in row.items() if value)
                        evidence = self._evidence(conn, document_id, text, csv_row=row_number, supporting=support)
                        self._insert_row(conn, table, row, evidence, data_kind)
                    except (DataError, sqlite3.IntegrityError) as exc:
                        raise DataError(f'CSV row {row_number}: {exc}; entire file rolled back') from exc
        except sqlite3.IntegrityError as exc:
            raise DataError(f'CSV document registration conflict: {exc}') from exc
        result = {'status': 'imported', 'document_id': document_id, 'sha256': digest,
                  'table': table, 'row_count': len(rows), 'data_kind': data_kind}
        self._log_completed('import_csv', result)
        return result

    def _support(self, conn, row, data_kind):
        doc, page = row.get('source_document_id', ''), row.get('source_page', '')
        if not doc and not page:
            return None
        if not doc or not page:
            raise DataError('source_document_id and source_page must be supplied together')
        original = conn.execute('SELECT kind, page_count, data_kind FROM documents WHERE document_id=?', (doc,)).fetchone()
        if original is None or original['kind'] != 'pdf':
            raise DataError(f'Unknown PDF source_document_id: {doc}')
        if data_kind == 'fact' and original['data_kind'] == 'demo':
            raise DataError('Demo PDF evidence cannot support a file labeled fact')
        try:
            page = int(page)
        except ValueError as exc:
            raise DataError('source_page must be a 1-based PDF page number') from exc
        if page < 1 or page > original['page_count']:
            raise DataError(f'source_page out of range: {page}')
        return doc, page

    def _entity(self, conn, entity_id, *, expected=None, name=None, data_kind=None):
        entity = conn.execute('''SELECT x.*, d.data_kind AS _data_kind, s.data_kind AS _support_kind
            FROM entities x JOIN evidence_chunks e ON e.evidence_id=x.evidence_id
            JOIN documents d ON d.document_id=e.document_id
            LEFT JOIN documents s ON s.document_id=e.supporting_document_id
            WHERE x.entity_id=?''', (entity_id,)).fetchone()
        if entity is None:
            raise DataError(f'Unknown entity_id: {entity_id}; import entities/companies first')
        if expected and entity['entity_type'] != expected:
            raise DataError(f'{entity_id} must have entity_type={expected}')
        if name and name != entity['name']:
            raise DataError(f'Name does not match registered entity {entity_id}')
        if data_kind == 'fact' and (entity['_data_kind'] == 'demo' or entity['_support_kind'] == 'demo'):
            raise DataError(f'File labeled fact cannot refer to demo entity {entity_id}')
        return entity

    def _value_type(self, row, data_kind):
        value_type = row.get('value_type') or ('scenario' if data_kind == 'demo' else 'fact')
        if value_type not in {'fact', 'estimate', 'scenario'}:
            raise DataError('value_type must be fact, estimate or scenario')
        if data_kind == 'demo' and value_type != 'scenario':
            raise DataError('Demo numerical rows must have value_type=scenario')
        note = row.get('assumption_note', '')
        if value_type != 'fact' and not note:
            raise DataError('estimate/scenario requires assumption_note')
        return value_type, note

    def _insert_row(self, conn, table, row, evidence, data_kind):
        import json
        status = row.get('verification_status') or 'pending'
        if status not in {'pending', 'verified'}:
            raise DataError('verification_status must be pending or verified')
        if table in {'entities', 'companies'}:
            entity_id = _id(row['entity_id'] if table == 'entities' else row['company_id'], 'entity_id')
            entity_type = row['entity_type'] if table == 'entities' else 'company'
            name = row['name'] if table == 'entities' else row['company_name']
            if entity_type not in {'company', 'material', 'product', 'process'}:
                raise DataError('Unsupported entity_type')
            aliases = [s.strip() for s in row.get('aliases', '').split('|') if s.strip()]
            existing = conn.execute('SELECT entity_type, name, grade FROM entities WHERE entity_id=?', (entity_id,)).fetchone()
            if existing is not None:
                if table != 'companies' or tuple(existing) != ('company', name, row.get('grade', '')):
                    raise DataError(f'entity_id already exists: {entity_id}')
                self._entity(conn, entity_id, data_kind=data_kind)
            else:
                conn.execute('INSERT INTO entities VALUES (?,?,?,?,?,?,?)',
                             (entity_id, entity_type, name, row.get('grade', ''),
                              json.dumps(aliases, ensure_ascii=False), status, evidence))
            if table == 'companies':
                conn.execute('INSERT INTO companies VALUES (?,?,?)',
                             (entity_id, row.get('security_code') or None, row['industry_stage']))
        elif table == 'relations':
            endpoints = []
            for key, name_key in [('upstream_id', 'upstream_name'), ('downstream_id', 'downstream_name')]:
                endpoints.append(self._entity(conn, row[key], name=row.get(name_key), data_kind=data_kind))
            grade = row.get('material_grade', '')
            if grade:
                materials = [entity for entity in endpoints if entity['entity_type'] == 'material']
                if not materials:
                    raise DataError('material_grade requires a material endpoint')
                # With two material endpoints this field describes the upstream material.
                if materials[0]['grade'] and grade != materials[0]['grade']:
                    raise DataError('Relation material_grade does not match registered material grade')
            start, end = iso_date(row.get('valid_from'), 'valid_from'), iso_date(row.get('valid_to'), 'valid_to')
            if start and end and start > end:
                raise DataError('valid_from must not be later than valid_to')
            conn.execute('INSERT INTO relations VALUES (?,?,?,?,?,?,?,?,?)',
                         (_id(row['relation_id'], 'relation_id'), row['upstream_id'], row['downstream_id'],
                          row['relation_type'], row.get('material_grade', ''), start, end, status, evidence))
        elif table == 'prices':
            entity = self._entity(conn, row['material_id'], expected='material', name=row.get('material_name'), data_kind=data_kind)
            if entity['grade'] and row['grade'] != entity['grade']:
                raise DataError('Price grade does not match registered material grade')
            value_type, note = self._value_type(row, data_kind)
            conn.execute('INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                         ('price_' + evidence[3:], row['material_id'], row['grade'], iso_date(row['date']),
                          _number(row['price'], 'price', True), row['unit'], _currency(row['currency']),
                          row['price_basis'], value_type, note, status, evidence))
        elif table == 'parameters':
            if not row.get('company_id') and not row.get('product_id'):
                raise DataError('Parameters require company_id or product_id')
            if row.get('company_id'):
                self._entity(conn, row['company_id'], expected='company', data_kind=data_kind)
            if row.get('product_id'):
                self._entity(conn, row['product_id'], expected='product', data_kind=data_kind)
            value_type, note = self._value_type(row, data_kind)
            value = _number(row['value'], 'value')
            if row['parameter_name'] == 'raw_material_cost_share':
                if row['unit'] != 'ratio' or not Decimal('0') <= Decimal(value) <= Decimal('1'):
                    raise DataError('raw_material_cost_share must use unit=ratio and a value from 0 to 1')
            conn.execute('INSERT INTO parameters VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                         (_id(row['parameter_id'], 'parameter_id'), row.get('company_id') or None,
                          row.get('product_id') or None, row['parameter_name'], value,
                          row['unit'], row['period'], value_type, note, status, evidence))
        elif table == 'metrics':
            self._entity(conn, row['company_id'], expected='company', data_kind=data_kind)
            value_type, note = self._value_type(row, data_kind)
            conn.execute('INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                         (_id(row['metric_id'], 'metric_id'), row['company_id'], row['metric_name'], row['period'],
                          _number(row['value'], 'value'), row['unit'], _currency(row['currency']),
                          value_type, note, status, evidence))

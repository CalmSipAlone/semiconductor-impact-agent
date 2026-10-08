"""Keyword evidence lookup; no embedding, LLM or business inference."""
from .errors import DataError
from .ingest import iso_date


class EvidenceQuery:
    def __init__(self, database):
        self.db = database

    def search(self, query='', *, document_id=None, limit=10, as_of=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise DataError('limit must be from 1 to 100')
        if not isinstance(query, str):
            raise DataError('query must be a string')
        if len(query) > 1000:
            raise DataError('Query exceeds 1000 characters')
        terms = query.split()
        if len(terms) > 20:
            raise DataError('At most 20 space-separated search terms')
        as_of = iso_date(as_of, 'as_of')
        if document_id is not None and (not isinstance(document_id, str) or not document_id.strip()):
            raise DataError('document_id must be a nonempty string or None')
        self.db.initialize()
        conditions, args = [], []
        for term in terms:
            # Literal substring search, not user-supplied SQL/LIKE wildcards.
            escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            conditions.append("e.text LIKE ? ESCAPE '\\'")
            args.append('%' + escaped + '%')
        if document_id:
            conditions.append('e.document_id=?')
            args.append(document_id)
        if as_of:
            conditions.extend(['d.published_on IS NOT NULL', 'd.published_on <= ?',
                               '(s.document_id IS NULL OR (s.published_on IS NOT NULL AND s.published_on <= ?))'])
            args.extend([as_of, as_of])
        where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
        sql = '''SELECT e.*, d.original_name, d.stored_path, d.source_url, d.published_on,
                        d.data_kind, d.sha256, s.sha256 AS supporting_sha256, s.original_name AS supporting_name,
                        s.stored_path AS supporting_path, s.source_url AS supporting_url
                 FROM evidence_chunks e JOIN documents d USING(document_id)
                 LEFT JOIN documents s ON s.document_id=e.supporting_document_id'''
        sql += where + ' ORDER BY d.original_name, e.document_id, COALESCE(e.pdf_page,e.csv_row) LIMIT ?'
        with self.db.connect() as conn:
            rows = conn.execute(sql, [*args, limit]).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item['file_path'] = str(self.db.path.parent / item.pop('stored_path'))
            support = item.pop('supporting_path')
            item['supporting_file_path'] = str(self.db.path.parent / support) if support else None
            results.append(item)
        self.db.verify_sources(results)
        return {'status': 'ok', 'query': query, 'count': len(results), 'results': results,
                'warnings': ['as_of excludes documents with unknown publication dates'] if as_of else []}

    def evidence(self, evidence_id):
        self.db.initialize()
        with self.db.connect() as conn:
            row = conn.execute('SELECT document_id FROM evidence_chunks WHERE evidence_id=?', (evidence_id,)).fetchone()
        if row is None:
            raise DataError(f'Unknown evidence_id: {evidence_id}')
        # Direct lookup avoids hiding an evidence item behind a search limit.
        with self.db.connect() as conn:
            evidence = dict(conn.execute('SELECT * FROM evidence_chunks WHERE evidence_id=?', (evidence_id,)).fetchone())
        evidence['document'] = self.db.document(evidence['document_id'])
        if evidence['supporting_document_id']:
            evidence['supporting_document'] = self.db.document(evidence['supporting_document_id'])
        return evidence

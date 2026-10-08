import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .errors import DataError, SourceIntegrityError

SCHEMA_VERSION = 1


class Database:
    def __init__(self, path):
        self.path = Path(path).resolve()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise DataError(f'Unsupported database version: {version}')
            if version == 0:
                tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if tables:
                    raise DataError('Existing database has no recognized schema; use another database path')
                schema = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
                conn.executescript('BEGIN;\n' + schema + f'\nPRAGMA user_version={SCHEMA_VERSION};\nCOMMIT;')

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def counts(self):
        self.initialize()
        tables = ('documents', 'evidence_chunks', 'entities', 'companies', 'relations', 'prices', 'parameters', 'metrics')
        with self.connect() as conn:
            return {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tables}

    def document(self, document_id):
        self.initialize()
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM documents WHERE document_id=?', (document_id,)).fetchone()
        if row is None:
            raise DataError(f'Unknown document_id: {document_id}')
        result = dict(row)
        result['file_path'] = self.verify_original(result['stored_path'], result['sha256'])
        return result

    def verify_original(self, stored_path, expected_hash):
        original = (self.path.parent / stored_path).resolve()
        source_root = (self.path.parent / 'sources').resolve()
        if not original.is_relative_to(source_root):
            raise SourceIntegrityError('Saved original path is outside the evidence directory')
        digest = hashlib.sha256()
        try:
            with original.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
        except OSError as exc:
            raise SourceIntegrityError(f'Saved original is unavailable: {original}: {exc}') from exc
        if digest.hexdigest() != expected_hash:
            raise SourceIntegrityError(f'Saved original hash mismatch: {original}')
        return str(original)

    def verify_sources(self, value):
        """Verify each distinct original in a response once, including PDF support."""
        checked = set()

        def visit(item):
            if isinstance(item, dict):
                for path_key, hash_key in [('file_path', 'sha256'),
                                           ('supporting_file_path', 'supporting_sha256')]:
                    if item.get(path_key) and item.get(hash_key):
                        key = (item[path_key], item[hash_key])
                        if key not in checked:
                            self.verify_original(*key)
                            checked.add(key)
                for child in item.values():
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)

        visit(value)

    def log(self, event):
        # CLI is single-process. One JSON line records one completed operation.
        path = self.path.parent / 'imports.jsonl'
        with path.open('a', encoding='utf-8') as stream:
            record = {'timestamp': datetime.now(timezone.utc).isoformat(),
                      'database': str(self.path), **event}
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

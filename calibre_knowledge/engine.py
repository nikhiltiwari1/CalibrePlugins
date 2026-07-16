"""Local indexing, retrieval, and OpenAI-compatible chat support.

This module intentionally has no Calibre or Qt imports.  It is therefore easy to
test and all book excerpts remain local until a configured chat endpoint is used.
"""
from __future__ import unicode_literals

import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


SUPPORTED_FORMATS = ('EPUB', 'TXT', 'HTML', 'HTM', 'PDF', 'MOBI', 'AZW3', 'DOCX', 'RTF')
WORD_RE = re.compile(r"[\w'-]{2,}", re.UNICODE)


def clean_text(value):
    value = re.sub(r'(?is)<(script|style|noscript).*?>.*?</\1>', ' ', value)
    value = re.sub(r'(?s)<[^>]+>', ' ', value)
    value = html.unescape(value)
    return re.sub(r'\s+', ' ', value).strip()


def chunks(text, size=1200, overlap=180):
    """Return readable overlapping chunks, rather than splitting words."""
    text = re.sub(r'\s+', ' ', text).strip()
    output, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind(' ', start + size - 220, end)
            if boundary > start:
                end = boundary
        part = text[start:end].strip()
        # Short essays and chapters should still be searchable.
        if len(part) >= 25:
            output.append(part)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return output


def extract_epub(path):
    pieces = []
    with zipfile.ZipFile(path) as book:
        names = sorted(n for n in book.namelist()
                       if n.lower().endswith(('.xhtml', '.html', '.htm')))
        for name in names:
            try:
                text = clean_text(book.read(name).decode('utf-8', 'replace'))
                if text:
                    pieces.append(text)
            except (KeyError, OSError, zipfile.BadZipFile):
                continue
    return '\n'.join(pieces)


def extract_plain(path):
    with open(path, 'rb') as stream:
        raw = stream.read()
    return clean_text(raw.decode('utf-8', 'replace'))


def calibre_convert_to_text(path, timeout=120):
    """Use the user's Calibre installation for formats that need conversion."""
    executable = os.path.join(os.path.dirname(sys.executable), 'ebook-convert.exe' if os.name == 'nt' else 'ebook-convert')
    if not os.path.exists(executable):
        executable = shutil.which('ebook-convert')
    if not executable:
        raise RuntimeError('Calibre conversion program was not found.')
    handle, target = tempfile.mkstemp(suffix='.txt', prefix='library-mentor-')
    os.close(handle)
    try:
        result = subprocess.run([executable, path, target], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout)
        if result.returncode:
            raise RuntimeError('Calibre could not convert this book to text.')
        return extract_plain(target)
    finally:
        try:
            os.remove(target)
        except OSError:
            pass


def extract_text(path, fmt):
    fmt = fmt.upper()
    if fmt == 'EPUB':
        return extract_epub(path)
    if fmt in ('TXT', 'HTML', 'HTM'):
        return extract_plain(path)
    return calibre_convert_to_text(path)


class LibraryIndex(object):
    def __init__(self, db_path):
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        self.connection = sqlite3.connect(db_path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self._create_schema()

    def _create_schema(self):
        self.connection.execute('CREATE TABLE IF NOT EXISTS status (key TEXT PRIMARY KEY, value TEXT)')
        self.connection.execute('CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5('
                                'book_id UNINDEXED, format UNINDEXED, title, author, field UNINDEXED, '
                                'part UNINDEXED, content, tokenize="porter unicode61")')
        self.connection.commit()

    def close(self):
        self.connection.close()

    def clear(self):
        self.connection.execute('DELETE FROM chunks')
        self.connection.execute('DELETE FROM status')
        self.connection.commit()

    def add_book(self, info):
        text = extract_text(info['path'], info['format'])
        if not text:
            return 0
        # Avoid runaway OCR/conversion output while preserving a substantial book portion.
        text = text[:1500000]
        rows = [(str(info['id']), info['format'], info['title'], info['author'], info['field'], str(number), part)
                for number, part in enumerate(chunks(text), 1)]
        self.connection.executemany('INSERT INTO chunks '
                                    '(book_id, format, title, author, field, part, content) VALUES (?, ?, ?, ?, ?, ?, ?)', rows)
        self.connection.commit()
        return len(rows)

    def finish(self, library_path, indexed_books, skipped_books):
        data = {'library_path': library_path, 'indexed_at': int(time.time()),
                'indexed_books': indexed_books, 'skipped_books': skipped_books}
        self.connection.execute('INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)',
                                ('summary', json.dumps(data)))
        self.connection.commit()

    def summary(self):
        row = self.connection.execute('SELECT value FROM status WHERE key=?', ('summary',)).fetchone()
        return json.loads(row[0]) if row else None

    def search(self, question, limit=6, book_id=None):
        terms = [term.lower() for term in WORD_RE.findall(question)]
        if not terms:
            return []
        match = ' OR '.join('"%s"' % term.replace('"', '') for term in terms[:14])
        condition, parameters = 'chunks MATCH ? ', [match]
        if book_id is not None:
            condition += 'AND book_id = ? '
            parameters.append(str(book_id))
        parameters.append(int(limit))
        try:
            rows = self.connection.execute(
                'SELECT book_id, format, title, author, field, part, content, bm25(chunks) '
                'FROM chunks WHERE ' + condition + 'ORDER BY bm25(chunks) LIMIT ?', parameters).fetchall()
        except sqlite3.OperationalError:
            return []
        return [{'book_id': row[0], 'format': row[1], 'title': row[2], 'author': row[3],
                 'field': row[4], 'part': row[5], 'content': row[6], 'score': row[7]} for row in rows]

    def sample_for_book(self, book_id, limit=5):
        rows = self.connection.execute(
            'SELECT book_id, format, title, author, field, part, content FROM chunks '
            'WHERE book_id=? ORDER BY CAST(part AS INTEGER) LIMIT ?', (str(book_id), int(limit))).fetchall()
        return [{'book_id': row[0], 'format': row[1], 'title': row[2], 'author': row[3],
                 'field': row[4], 'part': row[5], 'content': row[6]} for row in rows]


def context_for(results, maximum_chars=7600):
    blocks, used = [], 0
    for result in results:
        excerpt = result['content'][:1400]
        label = '[%s — %s, part %s]' % (result['title'], result['author'], result['part'])
        block = label + '\n' + excerpt
        if used + len(block) > maximum_chars:
            break
        blocks.append(block)
        used += len(block)
    return '\n\n'.join(blocks)


def ask_model(endpoint, model, api_key, system, prompt, timeout=75):
    endpoint = endpoint.rstrip('/')
    if not endpoint.endswith('/chat/completions'):
        endpoint += '/chat/completions'
    payload = json.dumps({'model': model, 'temperature': 0.2,
                          'messages': [{'role': 'system', 'content': system},
                                       {'role': 'user', 'content': prompt}]}).encode('utf-8')
    request = urllib.request.Request(endpoint, payload, {'Content-Type': 'application/json'})
    if api_key:
        request.add_header('Authorization', 'Bearer ' + api_key)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as err:
        raise RuntimeError('Could not contact the model at %s: %s' % (endpoint, err.reason))
    try:
        return data['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError('The model returned an unexpected response.')


def source_list(results):
    unique, seen = [], set()
    for item in results:
        key = (item['book_id'], item['part'])
        if key not in seen:
            seen.add(key)
            unique.append('• %s — %s (part %s)' % (item['title'], item['author'], item['part']))
    return '\n'.join(unique)

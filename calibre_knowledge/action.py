from __future__ import unicode_literals

import os
import traceback

from calibre.constants import config_dir
from calibre.gui2 import error_dialog, info_dialog, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.utils.config import JSONConfig
from qt.core import (QAction, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                     QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
                     QPlainTextEdit, QProgressDialog, QThread, QTimer, QVBoxLayout, Qt,
                     pyqtSignal)

from .engine import (LibraryIndex, SUPPORTED_FORMATS, ask_model, context_for,
                     source_list)


PREFS = JSONConfig('plugins/library_mentor')
PREFS.defaults.update({
    'endpoint': 'http://localhost:11434/v1/chat/completions',
    'model': 'llama3.2',
    'api_key': '',
    'daily_fields': '',
    'show_daily_on_start': False,
})


def index_path():
    return os.path.join(config_dir, 'plugins', 'library_mentor', 'library_index.sqlite')


class IndexWorker(QThread):
    progress = pyqtSignal(int, int, str)
    completed = pyqtSignal(int, int, int)

    def __init__(self, library_path, books, parent=None):
        QThread.__init__(self, parent)
        self.library_path, self.books = library_path, books
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        done, skipped, chunks = 0, 0, 0
        index = LibraryIndex(index_path())
        try:
            index.clear()
            for number, book in enumerate(self.books, 1):
                if self.cancelled:
                    break
                self.progress.emit(number, len(self.books), book['title'])
                try:
                    chunks += index.add_book(book)
                    done += 1
                except Exception:
                    skipped += 1
            if not self.cancelled:
                index.finish(self.library_path, done, skipped)
        finally:
            index.close()
        self.completed.emit(done, skipped, chunks)


class SettingsDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setWindowTitle('Library Mentor settings')
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.endpoint = QLineEdit(PREFS['endpoint'])
        self.model = QLineEdit(PREFS['model'])
        self.api_key = QLineEdit(PREFS['api_key'])
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.fields = QLineEdit(PREFS['daily_fields'])
        self.autostart = QCheckBox('Show the daily learning card after Calibre starts')
        self.autostart.setChecked(PREFS['show_daily_on_start'])
        form.addRow('Chat endpoint:', self.endpoint)
        form.addRow('Model:', self.model)
        form.addRow('API key (optional):', self.api_key)
        form.addRow('Daily fields (comma-separated):', self.fields)
        layout.addLayout(form)
        note = QLabel('Default endpoint is Ollama running on this computer. Leave Daily fields empty to rotate through your Calibre tags.')
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        PREFS['endpoint'] = self.endpoint.text().strip()
        PREFS['model'] = self.model.text().strip()
        PREFS['api_key'] = self.api_key.text().strip()
        PREFS['daily_fields'] = self.fields.text().strip()
        PREFS['show_daily_on_start'] = self.autostart.isChecked()
        QDialog.accept(self)


class AnswerDialog(QDialog):
    def __init__(self, parent, question, answer, sources):
        QDialog.__init__(self, parent)
        self.setWindowTitle('Library Mentor answer')
        self.resize(760, 580)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('<b>Question:</b> ' + question))
        output = QPlainTextEdit()
        output.setReadOnly(True)
        output.setPlainText(answer + '\n\nSources\n' + sources)
        layout.addWidget(output)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)


class LibraryMentorAction(InterfaceAction):
    name = 'Library Mentor'
    action_spec = ('Library Mentor', None, 'Ask your library and start today’s learning session', None)
    popup_type = QMenu

    def genesis(self):
        self.menu = QMenu(self.gui)
        ask = QAction('Ask your library…', self.gui)
        ask.triggered.connect(self.ask_question)
        self.menu.addAction(ask)
        daily = QAction('Today’s learning session', self.gui)
        daily.triggered.connect(self.daily_lesson)
        self.menu.addAction(daily)
        rebuild = QAction('Build / rebuild local index…', self.gui)
        rebuild.triggered.connect(self.rebuild_index)
        self.menu.addAction(rebuild)
        settings = QAction('Settings…', self.gui)
        settings.triggered.connect(self.settings)
        self.menu.addAction(settings)
        self.qaction.setMenu(self.menu)
        self.qaction.triggered.connect(self.ask_question)
        if PREFS['show_daily_on_start']:
            QTimer.singleShot(12000, self.daily_lesson)

    def current_db(self):
        return self.gui.current_db

    def book_records(self):
        db = self.current_db()
        records = []
        for book_id in db.all_book_ids():
            metadata = db.get_metadata(book_id, get_cover=False, cover_as_data=False)
            formats = [item.upper() for item in (db.formats(book_id) or '').split(',')]
            chosen = next((item for item in ('EPUB', 'PDF', 'AZW3', 'MOBI', 'DOCX', 'RTF', 'TXT', 'HTML', 'HTM') if item in formats), None)
            if not chosen:
                continue
            try:
                path = db.format_abspath(book_id, chosen)
            except Exception:
                continue
            if not path or not os.path.exists(path):
                continue
            tags = list(metadata.tags or [])
            records.append({'id': book_id, 'path': path, 'format': chosen,
                            'title': metadata.title or 'Untitled',
                            'author': ', '.join(metadata.authors or ['Unknown author']),
                            'field': tags[0] if tags else 'General', 'tags': tags})
        return records

    def ensure_index(self):
        index = LibraryIndex(index_path())
        summary = index.summary()
        index.close()
        if summary:
            return True
        info_dialog(self.gui, 'Library Mentor', 'Build the local index first. Select “Build / rebuild local index…” from the Library Mentor menu.', show=True)
        return False

    def rebuild_index(self):
        records = self.book_records()
        if not records:
            error_dialog(self.gui, 'Library Mentor', 'No supported ebook formats were found in this library.', show=True)
            return
        if not question_dialog(self.gui, 'Build local index',
                               'Index %d books? This reads their text locally. It can take time for large PDF-heavy libraries.' % len(records)):
            return
        self.progress = QProgressDialog('Preparing index…', 'Cancel', 0, len(records), self.gui)
        self.progress.setWindowTitle('Library Mentor')
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.show()
        self.worker = IndexWorker(self.current_db().library_path, records, self.gui)
        self.worker.progress.connect(self.index_progress)
        self.worker.completed.connect(self.index_complete)
        self.progress.canceled.connect(self.worker.cancel)
        self.worker.start()

    def index_progress(self, position, total, title):
        self.progress.setMaximum(total)
        self.progress.setValue(position)
        self.progress.setLabelText('Indexing %d of %d: %s' % (position, total, title[:90]))

    def index_complete(self, indexed, skipped, chunk_count):
        self.progress.close()
        info_dialog(self.gui, 'Local index ready',
                    'Indexed %d books into %d passages. Skipped %d books that could not be read.' % (indexed, chunk_count, skipped), show=True)

    def ask_question(self):
        if not self.ensure_index():
            return
        dialog = QDialog(self.gui)
        dialog.setWindowTitle('Ask your library')
        dialog.resize(620, 180)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Ask a question. Answers use passages from your indexed books and include sources.'))
        question = QPlainTextEdit()
        question.setPlaceholderText('For example: What are the practical steps for building a habit?')
        layout.addWidget(question)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        text = question.toPlainText().strip()
        if not text:
            return
        index = LibraryIndex(index_path())
        results = index.search(text)
        index.close()
        if not results:
            info_dialog(self.gui, 'No matching passages', 'No indexed passage matched that question. Try different terms or rebuild the index.', show=True)
            return
        prompt = ('Answer the question using only the supplied book passages. Be concise, practical, and honest about uncertainty. '
                  'Cite passages inline with the exact bracket labels already provided.\n\nQuestion: %s\n\nPassages:\n%s' %
                  (text, context_for(results)))
        try:
            answer = ask_model(PREFS['endpoint'], PREFS['model'], PREFS['api_key'],
                               'You are a careful personal librarian. Never invent facts not present in the passages.', prompt)
        except RuntimeError as err:
            answer = ('Relevant passages were found, but a model answer could not be generated.\n\n%s\n\n'
                      'Start Ollama or update Library Mentor settings, then ask again.' % err)
        AnswerDialog(self.gui, text, answer, source_list(results)).exec()

    def daily_candidates(self):
        allowed = [value.strip().lower() for value in PREFS['daily_fields'].split(',') if value.strip()]
        candidates = []
        for record in self.book_records():
            # A Calibre tag is a learning field. A multi-tagged book can take
            # part in the rotation for each of its fields, not only its first tag.
            for field in (record['tags'] or ['General']):
                if not allowed or field.lower() in allowed:
                    candidate = dict(record)
                    candidate['field'] = field
                    candidates.append(candidate)
        return candidates

    def daily_lesson(self):
        if not self.ensure_index():
            return
        candidates = self.daily_candidates()
        if not candidates:
            info_dialog(self.gui, 'No daily learning books', 'No books match the Daily fields setting.', show=True)
            return
        # A date-based choice gives one stable, repeatable book/field for each day.
        import datetime
        today = datetime.date.today().toordinal()
        fields = sorted(set(record['field'] for record in candidates), key=lambda value: value.lower())
        field = fields[today % len(fields)]
        books = sorted([record for record in candidates if record['field'] == field], key=lambda value: value['title'].lower())
        book = books[(today // max(1, len(fields))) % len(books)]
        index = LibraryIndex(index_path())
        passages = index.sample_for_book(book['id'])
        index.close()
        if not passages:
            info_dialog(self.gui, 'Book is not indexed', 'Today’s selected book has no readable indexed passages. Rebuild the index to refresh it.', show=True)
            return
        prompt = ('Create a focused 10-minute learning session from this book. Use only the passages. Give: '
                  '(1) a two-sentence orientation, (2) three key ideas, (3) one concrete work application, '
                  '(4) a 3-question self-check. Cite the supplied labels.\n\nField: %s\nBook: %s by %s\n\nPassages:\n%s' %
                  (field, book['title'], book['author'], context_for(passages)))
        try:
            lesson = ask_model(PREFS['endpoint'], PREFS['model'], PREFS['api_key'],
                               'You are an expert learning coach. Make the session clear and productive.', prompt)
        except RuntimeError as err:
            lesson = 'Today’s book: %s by %s\nField: %s\n\n%s\n\nModel unavailable: %s' % (book['title'], book['author'], field, context_for(passages), err)
        AnswerDialog(self.gui, 'Today: %s — %s' % (field, book['title']), lesson, source_list(passages)).exec()

    def settings(self):
        SettingsDialog(self.gui).exec()

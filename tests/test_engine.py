import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'calibre_knowledge'))
from engine import LibraryIndex, chunks, extract_epub


class EngineTests(unittest.TestCase):
    def test_chunks_keep_meaningful_text(self):
        result = chunks('A ' * 2000, size=300, overlap=40)
        self.assertGreater(len(result), 3)
        self.assertTrue(all(len(item) >= 25 for item in result))

    def test_epub_extraction_and_search(self):
        with tempfile.TemporaryDirectory() as directory:
            epub = os.path.join(directory, 'book.epub')
            with zipfile.ZipFile(epub, 'w') as archive:
                archive.writestr('chapter.xhtml', '<html><body><h1>Focus</h1><p>Deliberate practice improves skill through feedback.</p></body></html>')
            self.assertIn('Deliberate practice', extract_epub(epub))
            index = LibraryIndex(os.path.join(directory, 'index.sqlite'))
            index.add_book({'id': 9, 'path': epub, 'format': 'EPUB', 'title': 'Practice', 'author': 'Author', 'field': 'Learning'})
            found = index.search('How does practice improve skill?')
            index.close()
            self.assertEqual(found[0]['title'], 'Practice')


if __name__ == '__main__':
    unittest.main()

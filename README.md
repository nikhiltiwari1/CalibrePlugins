# Library Mentor for Calibre

Library Mentor is a local-first Calibre interface plugin. It indexes readable book text from the active Calibre library, retrieves relevant passages for a question, and has an optional daily 10-minute learning session that rotates through subjects (Calibre tags) and books.

## Install

1. Open Calibre → **Preferences** → **Plugins** → **Load plugin from file**.
2. Choose `Library Mentor.zip` from this folder and accept the warning.
3. Restart Calibre. The **Library Mentor** toolbar/menu action appears.
4. Open its menu and select **Build / rebuild local index…** while your `D:\Calibre Library` is the active library.
5. Install and start [Ollama](https://ollama.com/) if you want private local AI answers, then run `ollama pull llama3.2`. The default settings already use Ollama's local OpenAI-compatible endpoint.

You may instead set any OpenAI-compatible endpoint, model name, and optional API key from **Library Mentor → Settings**. In that case, relevant book excerpts are sent to that service only when you ask a question or create a learning session.

## Daily learning

Select **Today’s learning session** to receive a stable daily session. By default, it rotates across the first Calibre tag on each book. In Settings, you can restrict it to named tags, such as `Management, Python, History`, and choose whether it should open automatically when Calibre starts.

## Notes

- Index data is stored in Calibre's local plugin configuration directory, not in your library.
- EPUB, TXT and HTML are read directly. PDF, MOBI, AZW3, DOCX and RTF use Calibre's own converter, so they can take longer and some protected or image-only files may be skipped.
- Rebuild the index after adding significant new books.

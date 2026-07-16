# Library Mentor for Calibre

> Turn the books you already own into a focused, source-backed learning system.

**Library Mentor** is a local-first [Calibre](https://calibre-ebook.com/) plugin that lets you ask questions across your ebook library and receive answers grounded in passages from your books. It also creates one practical, 10-minute learning session every day by rotating through your Calibre tags and books.

It is designed for readers who want less searching, less passive reading, and more useful recall.

## What you can do

- **Ask your library** — ask a plain-English question and get a concise answer with the book and passage used for each source.
- **Learn one useful thing a day** — get a stable daily lesson from a selected subject and book, including key ideas, a work application, and a self-check.
- **Use your existing organisation** — Calibre tags become learning fields such as `Leadership`, `Python`, `History`, or `Finance`.
- **Keep control of your data** — the searchable index stays on your computer. With the default Ollama setup, the AI model is local too.
- **Work across common formats** — EPUB, TXT, HTML, PDF, MOBI, AZW3, DOCX, and RTF are supported where Calibre can read or convert them.

## How it works

```text
Your Calibre library
        ↓
Local text index on your computer
        ↓
Relevant book passages are retrieved
        ↓
Your chosen AI model writes an answer
        ↓
Answer + cited book passages
```

The plugin does not make up a library-wide answer from metadata alone: it first retrieves matching passages from the books that you have indexed. Every result lists its sources so you can quickly verify or continue reading.

## Privacy at a glance

| Setup | Where the index lives | Where passages go |
| --- | --- | --- |
| Default: Ollama on this computer | Your Calibre plugin data folder | Nowhere outside your computer |
| Custom OpenAI-compatible provider | Your Calibre plugin data folder | Only the passages needed for the question or lesson are sent to that provider |

Library Mentor never modifies the books in your Calibre library. Rebuilding the index only reads book content and refreshes its separate local search database.

## Requirements

- Calibre 6.0 or later
- A Calibre library containing supported ebook formats
- An AI chat endpoint compatible with the OpenAI chat-completions API

For the simplest private setup, install [Ollama](https://ollama.com/) and download a model:

```powershell
ollama pull llama3.2
```

The plugin is preconfigured for Ollama at `http://localhost:11434/v1/chat/completions` using the `llama3.2` model.

## Installation

1. Download the included [Library Mentor.zip](./Library%20Mentor.zip). Future releases may also provide the same file as a release asset.
2. In Calibre, open **Preferences → Plugins → Load plugin from file**.
3. Choose `Library Mentor.zip` and accept Calibre’s third-party-plugin warning.
4. Restart Calibre.
5. Add **Library Mentor** to a toolbar from **Preferences → Toolbars & menus** if it does not already appear where you want it.

> The plugin works with whichever library is currently open in Calibre. Open your library (for example, `D:\Calibre Library`) before building the index.

## Quick start

### 1. Build the local index

Open the **Library Mentor** menu and select **Build / rebuild local index…**. The plugin reads your available book formats and creates a local searchable passage index.

The first run may take a while for a large, PDF-heavy library. You can keep using Calibre while it runs; a progress window shows the current book and lets you cancel safely.

### 2. Ask a question

Choose **Ask your library…** and ask naturally:

```text
What are the most practical ways to build a durable habit?
```

```text
Explain the difference between supervised and unsupervised learning.
```

```text
What management advice do my books give for handling difficult conversations?
```

Library Mentor retrieves the strongest matching passages, asks your configured model to answer only from that material, and shows the sources below the response.

### 3. Use today’s learning session

Choose **Today’s learning session** for a focused 10-minute study card. It includes:

1. A short orientation to today’s topic
2. Three key ideas from the selected book
3. One concrete work or life application
4. A three-question self-check

The selection is deterministic for the day: reopening it gives the same subject and book, so you can return to it later without losing your place.

## Organise your daily learning with Calibre tags

Each Calibre tag is treated as a learning field. A book with both `Python` and `Data Science` tags can appear in either field’s rotation.

By default, Library Mentor rotates through every tagged subject it can find. To focus the routine, open **Library Mentor → Settings** and enter a comma-separated list in **Daily fields**, for example:

```text
Leadership, Python, Decision Making
```

You can also choose to show the daily learning card automatically after Calibre starts.

## Settings

| Setting | Purpose |
| --- | --- |
| **Chat endpoint** | The full URL of an OpenAI-compatible chat-completions endpoint |
| **Model** | The model name used by that endpoint |
| **API key** | Optional credential for a remote endpoint; not needed for default local Ollama |
| **Daily fields** | Optional comma-separated Calibre tags to include in daily rotation |
| **Show daily card on start** | Opens the current day’s study session shortly after Calibre launches |

## Supported formats

| Format | Reading method |
| --- | --- |
| EPUB, TXT, HTML | Read directly by the plugin |
| PDF, MOBI, AZW3, DOCX, RTF | Converted to text through Calibre’s conversion engine |

Image-only scans, protected books, and files Calibre cannot convert may be skipped. The build summary reports how many books were indexed and skipped.

## Troubleshooting

**“Build the local index first”**  
Use **Build / rebuild local index…** once after installation and whenever you add a meaningful group of books.

**“Could not contact the model”**  
For Ollama, confirm that it is running and that the configured model is installed. For a remote provider, verify the endpoint, model name, and API key in **Settings**.

**A book is missing from results**  
Check that it has a supported format and then rebuild the index. A protected or image-only file may not expose readable text.

**The answer is not specific enough**  
Ask with distinctive terms, names, or concepts from the book. This improves retrieval before the model writes an answer.

## Project layout

```text
calibre_knowledge/
  __init__.py       Plugin metadata and Calibre entry point
  action.py         Calibre menus, dialogs, indexing flow, and daily lessons
  engine.py         Text extraction, local search, retrieval, and model client
tests/
  test_engine.py    Search and EPUB extraction tests
Library Mentor.zip  Installable Calibre plugin archive
```

## Development

The core indexing engine is deliberately independent of Calibre’s interface code, making it straightforward to test:

```powershell
python -m unittest discover -s tests -v
```

After changing plugin source files, rebuild `Library Mentor.zip` before loading it into Calibre.

## Status

Library Mentor is an early, practical plugin for personal libraries. Feedback on retrieval quality, format support, and daily-learning workflows is especially welcome.

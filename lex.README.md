# lex.py - Lexeme Statistics Generator

Generates search index statistics from site content for the v0plex documentation site.

## Overview

This tool analyzes all markdown pages from `site-data.json`, tokenizes the content (supporting both English and Chinese), and builds a word-to-pages index with Shannon entropy scoring for better search relevance.

## Usage

### Basic Usage

```bash
# Run with default settings
python public/lex.py

# Or via npm script
npm run lex:gen
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--site-data-json` | `public/vmdjson/site-data.json` | Path to site data JSON |
| `--stopwords` | `public/stopwords.txt` | Path to stopwords list |
| `--ignore-files` | `public/ignore_files.txt` | Path to ignore list |
| `--no-jieba` | disabled | Disable jieba for Chinese tokenization |
| `--keep-punctuation` | disabled | Keep punctuation in tokens |
| `--min-token-len` | 1 | Minimum token length |
| `--min-ascii-len` | 2 | Minimum length for ASCII words |
| `--exts` | `.md` | Comma-separated file extensions |
| `--max-words-per-page` | 1500 | Cap words per page (0 = unlimited) |
| `--min-total` | 1 | Minimum total word count |
| `--min-df` | 1 | Minimum document frequency |
| `--max-df-ratio` | 1.0 | Maximum document frequency ratio |
| `--min-entropy` | 0.0 | Minimum Shannon entropy |
| `--top-pages-per-word` | 10 | Max pages stored per word |
| `--max-words-global` | 3000 | Max words in index |

### Examples

```bash
# Index with stricter filtering
python public/lex.py --min-token-len 2 --min-ascii-len 3

# Limit index size for smaller bundle
python public/lex.py --max-words-global 2000 --top-pages-per-word 5

# Use custom site data location
python public/lex.py --site-data-json ./custom/site-data.json
```

## Output Format

The tool adds a `lexemeStats` field to `site-data.json`:

```json
{
  "lexemeStats": {
    "version": 3,
    "pageIndex": {
      "page_hash": { "title": "...", "path": "/..." }
    },
    "byWord": {
      "search_term": {
        "t": 10,      // total occurrences
        "df": 3,      // document frequency
        "dfr": 0.1,   // document frequency ratio
        "H": 2.5,     // Shannon entropy
        "p": [{"h": "page_hash", "c": 5}]  // pages with counts
      }
    },
    "selectedWords": ["word1", "word2", ...]
  }
}
```

## Stopwords

Create a `stopwords.txt` file to exclude common words:

```
the
is
at
which
on
```

## Ignore Files

Create an `ignore_files.txt` file to exclude specific files:

```
README.md
CHANGELOG.md
draft/*.md
```

## Dependencies

- Python 3.8+
- jieba (optional, for Chinese tokenization)

```bash
pip install jieba
```

## How It Works

1. **Collect Pages**: Reads navigation from `site-data.json`
2. **Tokenize**: Splits text into words (English) or characters/jieba segments (Chinese)
3. **Filter**: Removes stopwords, short tokens, and punctuation
4. **Score**: Calculates Shannon entropy to prioritize discriminative terms
5. **Shrink**: Limits pages per word and total words to control JSON size
6. **Output**: Writes stats back to `site-data.json`

## Integration

This tool runs automatically during the build process:

```bash
npm run build  # Runs vmd:gen, then lex:gen, then next build
```

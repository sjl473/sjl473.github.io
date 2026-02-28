import os
import re
import json
import argparse
import math
from collections import Counter, defaultdict
from typing import Tuple, Dict, Any, List

# Optional dependency:
#   pip install jieba
try:
    import jieba  # type: ignore
except Exception:
    jieba = None


def _load_lines_set(path_: str) -> set:
    s = set()
    try:
        with open(path_, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                s.add(line)
                s.add(line.lower())
    except OSError:
        return set()
    return s


def _load_ignore_lists(path_: str) -> tuple[set, set]:
    ignored_basenames = set()
    ignored_relpaths = set()
    try:
        with open(path_, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                norm = line.replace("\\", "/").lstrip("./")
                ignored_basenames.add(os.path.basename(norm))
                ignored_relpaths.add(norm)
    except OSError:
        return set(), set()
    return ignored_basenames, ignored_relpaths


def _make_tokenizer(
    *,
    use_jieba: bool,
    keep_punctuation: bool,
    lowercase_ascii: bool,
    min_ascii_len: int,
    min_token_len: int,
    stopwords: set,
):
    cjk_re = re.compile(r"[\u4e00-\u9fff]")
    en_token_re = re.compile(
        r"[A-Za-z]+(?:'[A-Za-z]+)?"
        r"|[0-9]+(?:\.[0-9]+)?"
        r"|[^\s]"
    )
    ascii_word_re = re.compile(r"^[A-Za-z]+(?:'[A-Za-z]+)?$")

    def is_cjk(ch: str) -> bool:
        return bool(cjk_re.match(ch))

    def split_mixed_runs(text: str):
        if not text:
            return []
        runs = []
        buf = [text[0]]
        last_is_cjk = is_cjk(text[0])
        for ch in text[1:]:
            cur_is_cjk = is_cjk(ch)
            if cur_is_cjk == last_is_cjk:
                buf.append(ch)
            else:
                runs.append("".join(buf))
                buf = [ch]
                last_is_cjk = cur_is_cjk
        runs.append("".join(buf))
        return runs

    def tokenize(text: str):
        tokens = []
        for run in split_mixed_runs(text):
            if not run.strip():
                continue
            if is_cjk(run[0]):
                if use_jieba and jieba is not None:
                    tokens.extend([t for t in jieba.cut(run, cut_all=False) if t.strip()])
                else:
                    tokens.extend([ch for ch in run if ch.strip()])
            else:
                tokens.extend(en_token_re.findall(run))
        return [t for t in tokens if t and not t.isspace()]

    def is_punctuation(tok: str) -> bool:
        if len(tok) == 1 and not tok.isalnum() and tok != "_":
            return True
        if tok in {"，", "。", "！", "？", "；", "：", "、", "（", "）", "《", "》", "“", "”", "‘", "’"}:
            return True
        return False

    def normalize_and_filter(tok: str):
        tok = tok.strip()
        if not tok:
            return None

        if not keep_punctuation and is_punctuation(tok):
            return None

        # Filter out tokens that are too short
        if len(tok) < min_token_len:
            return None

        # Additional rules for ASCII words
        if ascii_word_re.match(tok):
            tok = tok.lower() if lowercase_ascii else tok
            if len(tok) < min_ascii_len:
                return None

        if tok in stopwords:
            return None

        return tok

    def tokenize_filtered(text: str):
        for t in tokenize(text):
            t2 = normalize_and_filter(t)
            if t2 is not None:
                yield t2

    return tokenize_filtered


def _collect_pages_from_navigation(nav: Any) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []

    def walk(node: Any):
        if not isinstance(node, dict):
            return
        node_type = node.get("type")
        if node_type == "page":
            pages.append(node)
            return
        children = node.get("children")
        if isinstance(children, list):
            for ch in children:
                walk(ch)

    if isinstance(nav, list):
        for n in nav:
            walk(n)
    elif isinstance(nav, dict):
        walk(nav)

    return pages


def build_lexeme_stats_from_site_data(
    *,
    project_root: str,
    site_data: Dict[str, Any],
    stopwords_file: str,
    ignore_files_list: str,
    use_jieba: bool,
    keep_punctuation: bool,
    lowercase_ascii: bool,
    min_ascii_len: int,
    min_token_len: int,
    encoding: str,
    include_exts: Tuple[str, ...],
    max_words_per_page: int,
    # Shannon/entropy selection params
    min_total: int,
    min_df: int,
    max_df_ratio: float,
    min_entropy: float,
    # Reduce JSON size
    top_pages_per_word: int,
    max_words_global: int,
) -> Dict[str, Any]:
    stopwords = _load_lines_set(stopwords_file)
    ignored_basenames, ignored_relpaths = _load_ignore_lists(ignore_files_list)

    tokenize_filtered = _make_tokenizer(
        use_jieba=use_jieba,
        keep_punctuation=keep_punctuation,
        lowercase_ascii=lowercase_ascii,
        min_ascii_len=min_ascii_len,
        min_token_len=min_token_len,
        stopwords=stopwords,
    )

    pages = _collect_pages_from_navigation(site_data.get("navigation", []))
    print(f"[lex] pages_in_site_data={len(pages)}")

    include_exts_lc = tuple(e.lower() for e in include_exts)

    # Collect word counts across pages for entropy calculation
    word_page_counts: Dict[str, Dict[str, int]] = defaultdict(dict)  # word -> {pageHash: count}

    # Store deduplicated title/path data in a page index to reduce site-data.json length
    page_index: Dict[str, Dict[str, str]] = {}

    processed_pages = 0
    skipped_pages = 0

    for p in pages:
        page_hash = str(p.get("hash") or "").strip()
        md_path = str(p.get("mdPath") or "").strip()
        page_title = str(p.get("title") or "").strip()
        page_path = str(p.get("path") or "").strip()

        if not page_hash or not md_path:
            skipped_pages += 1
            continue

        if not md_path.lower().endswith(include_exts_lc):
            skipped_pages += 1
            continue

        md_norm = md_path.replace("\\", "/").lstrip("./")
        if os.path.basename(md_norm) in ignored_basenames:
            skipped_pages += 1
            continue
        if md_norm in ignored_relpaths:
            skipped_pages += 1
            continue

        abs_md = os.path.abspath(os.path.join(project_root, md_path))
        if not os.path.isfile(abs_md):
            print(f"[lex] missing_md_file: {md_path}")
            skipped_pages += 1
            continue

        try:
            with open(abs_md, "r", encoding=encoding, errors="ignore") as f:
                text = f.read()
        except OSError:
            skipped_pages += 1
            continue

        c = Counter(tokenize_filtered(text))

        # Optional size cap (keeps only top-N words per page)
        if max_words_per_page > 0 and len(c) > max_words_per_page:
            c = Counter(dict(c.most_common(max_words_per_page)))

        page_index[page_hash] = {"title": page_title, "path": page_path}

        for w, cnt in c.items():
            word_page_counts[w][page_hash] = int(cnt)

        processed_pages += 1

    print(f"[lex] processed_pages={processed_pages}, skipped_pages={skipped_pages}")
    total_pages = max(1, processed_pages)

    # Entropy calculation + filtering out words that are too common or too rare
    candidates: Dict[str, Any] = {}

    for w, pc in word_page_counts.items():
        df = len(pc)
        total = sum(pc.values())
        if total <= 0:
            continue

        # Filter out rare words
        if total < min_total:
            continue
        if df < min_df:
            continue

        # Filter out words that appear on too many pages (stop words)
        if (df / total_pages) > max_df_ratio:
            continue

        # Shannon entropy (page distribution)
        H = 0.0
        for cnt_i in pc.values():
            p_i = cnt_i / total
            H -= p_i * math.log(p_i, 2)

        if H < min_entropy:
            continue

        # Reduce JSON length by keeping only the top pages per word
        pages_list = [{"h": h, "c": int(cnt)} for h, cnt in pc.items()]
        pages_list.sort(key=lambda x: x.get("c", 0), reverse=True)
        if top_pages_per_word > 0:
            pages_list = pages_list[:top_pages_per_word]

        candidates[w] = {
            "t": int(total),               # total
            "df": int(df),                 # document frequency
            "dfr": float(df / total_pages),
            "H": float(H),                 # entropy
            "p": pages_list,               # pages: [{h,c}]
        }

    # Global trim: select words with highest entropy to further shrink JSON
    words_sorted = sorted(candidates.keys(), key=lambda ww: candidates[ww]["H"], reverse=True)
    if max_words_global > 0:
        words_sorted = words_sorted[:max_words_global]

    by_word = {w: candidates[w] for w in words_sorted}

    print(f"[lex] unique_words_indexed(after_filter+shrink)={len(by_word)}")

    return {
        "version": 3,
        "source": {
            "mode": "byWord-only-with-shannon-filter+shrink",
            "includeExts": list(include_exts_lc),
            "maxWordsPerPage": int(max_words_per_page),
            "totalPages": int(total_pages),
            "filters": {
                "minTokenLen": int(min_token_len),
                "minAsciiLen": int(min_ascii_len),
                "minTotal": int(min_total),
                "minDf": int(min_df),
                "maxDfRatio": float(max_df_ratio),
                "minEntropy": float(min_entropy),
            },
            "shrink": {
                "topPagesPerWord": int(top_pages_per_word),
                "maxWordsGlobal": int(max_words_global),
            },
        },
        "pageIndex": page_index,  # hash -> {title,path}
        "byWord": by_word,        # word -> compact stats
        "selectedWords": words_sorted,
    }


def _main():
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(here, ".."))

    parser = argparse.ArgumentParser(
        description="Compute Shannon-entropy-based byWord lexeme stats and write into public/vmdjson/site-data.json."
    )
    parser.add_argument(
        "--site-data-json",
        default=os.path.join(project_root, "public", "vmdjson", "site-data.json"),
        help="Path to public/vmdjson/site-data.json",
    )
    parser.add_argument("--stopwords", default=os.path.join(here, "stopwords.txt"))
    parser.add_argument("--ignore-files", default=os.path.join(here, "ignore_files.txt"))
    parser.add_argument("--no-jieba", action="store_true")
    parser.add_argument("--keep-punctuation", action="store_true")

    # Length limit parameters - lowered defaults to be more permissive
    parser.add_argument("--min-token-len", type=int, default=1, help="Minimum token length. Default: 1")
    parser.add_argument("--min-ascii-len", type=int, default=2, help="Minimum length for ASCII words. Default: 2")

    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("--exts", default=".md", help="Comma-separated extensions to include (default: .md)")
    parser.add_argument(
        "--max-words-per-page",
        type=int,
        default=1500,
        help="Cap words counted per page (0 = no limit). Default: 1500",
    )

    # Shannon filter parameters
    parser.add_argument("--min-total", type=int, default=1, help="Discard words with total count below this value. Default: 1")
    parser.add_argument("--min-df", type=int, default=1, help="Discard words that appear in fewer pages than this value. Default: 1")
    parser.add_argument(
        "--max-df-ratio",
        type=float,
        default=1.0,
        help="Discard words appearing in more than this ratio of total pages (e.g. 1.0 means don't discard any). Default: 1.0",
    )
    parser.add_argument(
        "--min-entropy",
        type=float,
        default=0.0,
        help="Minimum Shannon entropy based on page distribution. Default: 0.0 (no entropy filter)",
    )

    # Output size limits
    parser.add_argument(
        "--top-pages-per-word",
        type=int,
        default=10,
        help="Maximum number of top occurrence pages to store per word (0 = no limit). Default: 10",
    )
    parser.add_argument(
        "--max-words-global",
        type=int,
        default=3000,
        help="Maximum number of global words to keep, prioritized by entropy. Default: 3000",
    )

    args = parser.parse_args()
    site_data_json_abs = os.path.abspath(args.site_data_json)

    with open(site_data_json_abs, "r", encoding="utf-8") as f:
        site_data = json.load(f)
        if not isinstance(site_data, dict):
            raise ValueError("site-data.json root must be a JSON object")

    exts = tuple(e.strip() for e in str(args.exts).split(",") if e.strip())
    if not exts:
        exts = (".md",)

    stats = build_lexeme_stats_from_site_data(
        project_root=project_root,
        site_data=site_data,
        stopwords_file=args.stopwords,
        ignore_files_list=args.ignore_files,
        use_jieba=not args.no_jieba,
        keep_punctuation=bool(args.keep_punctuation),
        lowercase_ascii=True,
        min_ascii_len=int(args.min_ascii_len),
        min_token_len=int(args.min_token_len),
        encoding=str(args.encoding),
        include_exts=exts,
        max_words_per_page=int(args.max_words_per_page),
        min_total=int(args.min_total),
        min_df=int(args.min_df),
        max_df_ratio=float(args.max_df_ratio),
        min_entropy=float(args.min_entropy),
        top_pages_per_word=int(args.top_pages_per_word),
        max_words_global=int(args.max_words_global),
    )

    site_data["lexemeStats"] = stats

    os.makedirs(os.path.dirname(site_data_json_abs) or ".", exist_ok=True)
    with open(site_data_json_abs, "w", encoding="utf-8") as f:
        json.dump(site_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[lex] updated site-data.json with lexemeStats(shrinked): {site_data_json_abs}")


if __name__ == "__main__":
    _main()
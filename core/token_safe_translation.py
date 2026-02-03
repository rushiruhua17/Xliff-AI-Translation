from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class SplitResult:
    text_chunks: List[str]
    tokens: List[str]


def split_by_known_tokens(text: str, tags_map: Dict[str, str]) -> SplitResult:
    known: Set[str] = set((tags_map or {}).keys())
    tokens: List[str] = []
    chunks: List[str] = []
    buf: List[str] = []

    i = 0
    n = len(text or "")
    s = text or ""

    def flush_buf(force: bool = False):
        if force or buf or not chunks:
            chunks.append("".join(buf))
            buf.clear()

    while i < n:
        ch = s[i]
        if ch != "{":
            buf.append(ch)
            i += 1
            continue

        j = i + 1
        if j >= n or not s[j].isdigit():
            buf.append(ch)
            i += 1
            continue

        while j < n and s[j].isdigit():
            j += 1
        if j >= n or s[j] != "}":
            buf.append(ch)
            i += 1
            continue

        key = s[i + 1 : j]
        if key in known:
            flush_buf()
            tokens.append("{" + key + "}")
            i = j + 1
            continue

        buf.append(ch)
        i += 1

    flush_buf(force=True)

    if len(chunks) != len(tokens) + 1:
        raise ValueError("Split invariant violated")

    return SplitResult(text_chunks=chunks, tokens=tokens)


def reassemble_from_chunks(chunks: List[str], tokens: List[str]) -> str:
    if len(chunks) != len(tokens) + 1:
        raise ValueError("Reassemble invariant violated")
    out: List[str] = []
    for i, chunk in enumerate(chunks):
        out.append(chunk or "")
        if i < len(tokens):
            out.append(tokens[i])
    return "".join(out)


def strip_known_tokens(text: str, tags_map: Dict[str, str]) -> str:
    known: Set[str] = set((tags_map or {}).keys())
    if not known:
        return text or ""

    s = text or ""
    out: List[str] = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] != "{":
            out.append(s[i])
            i += 1
            continue

        j = i + 1
        if j < n and s[j].isdigit():
            while j < n and s[j].isdigit():
                j += 1
            if j < n and s[j] == "}":
                key = s[i + 1 : j]
                if key in known:
                    i = j + 1
                    continue

        out.append(s[i])
        i += 1

    return "".join(out)

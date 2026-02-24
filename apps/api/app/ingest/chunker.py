from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class ChunkConfig:
    chunk_chars: int = 700
    overlap_chars: int = 100


def normalize_text_for_chunking(text: str) -> str:
    """Normalize extraction artifacts before chunking."""
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # Normalize Unicode spacing artifacts often found in PDFs.
    normalized = (
        normalized.replace("\u00A0", " ")
        .replace("\u2007", " ")
        .replace("\u202F", " ")
    )
    normalized = re.sub(r"[\u200B-\u200D\uFEFF]", "", normalized)

    # Soft hyphen is a discretionary hyphen and should not survive into chunks.
    normalized = normalized.replace("\u00AD", "")

    # Join words broken by line-wrap hyphenation (e.g. "inter-\nnational").
    normalized = re.sub(
        r"(?<=[A-Za-z0-9])-\s*\n\s*(?=[A-Za-z0-9])",
        "",
        normalized,
    )

    # Collapse noisy spacing while preserving paragraph/newline boundaries.
    normalized = re.sub(r"[ \t\f\v]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def lc_recursive_ch_text(text: str, cfg: ChunkConfig):
    """
    Uses langchain's RecursiveCharacterTextSplitter to split text into chunks.
    This is more sophisticated than our simple chunking and can split on newlines, spaces, etc.
    """
    text = normalize_text_for_chunking(text)
    if not text:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_chars,
        chunk_overlap=cfg.overlap_chars,
        separators=["\n\n", "\n", " ", ""],
    )
    return splitter.split_text(text)


def chunk_text(text: str, cfg: ChunkConfig) -> List[str]:
    """
    Simple, robust text chunking based on character count with overlap.
    Good enough for v0 ingestion
    """
    text = normalize_text_for_chunking(text)

    if not text:
        return []

    chunks: List[str] = []
    i = 0
    n = len(text)

    print(f"Total text length: {n} characters")

    while i < n:
        end = min(i + cfg.chunk_chars, n)
        chunk = text[i:end]

        # If we are not at the end, try to break at the last newline or space
        last_newline = chunk.rfind("\n")
        last_space = chunk.rfind("\n\n")
        split_pos = max(last_newline, last_space)

        if split_pos != -1 and split_pos > cfg.chunk_chars * 0.6:
            end = i + split_pos + 1  # +1 to include the split character
        chunk = text[i:end].strip()
        print(f"Chunk from {i} to {end} (length {len(chunk)})")
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break

        i = max(end - cfg.overlap_chars, 0)  # Move back by overlap

    return chunks

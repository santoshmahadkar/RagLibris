"""Normalize extracted document text and split it into retrieval-sized chunks.

The generic path favors paragraph boundaries, falling back to word windows for
oversized paragraphs. Its structured output is consumed by the indexing
pipeline, which embeds each chunk and stores the text with document metadata.
"""

import re


# ============================================================
# CONFIGURATION
# ============================================================

# Chunk sizes and overlap are measured in whitespace-separated words.
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 100


# ============================================================
# 1. TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    """Clean extracted text while preserving paragraph-separating newlines.

    Normalizes line endings and tabs, removes non-printable characters, trims
    each line, collapses repeated spaces, and reduces consecutive blank lines.

    Args:
        text: Text extracted from a source document.

    Returns:
        Normalized text, or an empty string when the input is empty.
    """

    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Remove non-printable characters
    text = "".join(
        char
        for char in text
        if char.isprintable() or char == "\n"
    )

    cleaned_lines = []

    for line in text.split("\n"):

        # Remove leading/trailing whitespace
        line = line.strip()

        # Collapse multiple spaces
        line = re.sub(r"[ ]+", " ", line)

        cleaned_lines.append(line)

    # Remove excessive blank lines
    final_lines = []

    previous_blank = False

    for line in cleaned_lines:

        if line == "":

            if not previous_blank:
                final_lines.append("")

            previous_blank = True

        else:

            final_lines.append(line)

            previous_blank = False

    return "\n".join(final_lines).strip()


# ============================================================
# 2. WORD-BASED CHUNKING
# ============================================================

def chunk_by_words(
    text,
    chunk_size=DEFAULT_CHUNK_SIZE,
    overlap=DEFAULT_OVERLAP
):
    """Split text into word-count windows with overlap between adjacent chunks.

    The overlap retains boundary context that would otherwise be lost when a
    document is divided into separate retrieval units.

    Args:
        text: Text to split.
        chunk_size: Maximum number of words in each chunk.
        overlap: Number of trailing words repeated at the start of the next.

    Returns:
        A list of non-empty word chunks; empty or whitespace-only input yields
        an empty list.

    Raises:
        ValueError: If a non-empty input has an invalid chunk size or overlap.
    """

    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size."
        )

    words = text.split()

    if not words:
        return []

    chunks = []

    start = 0

    while start < len(words):

        end = min(
            start + chunk_size,
            len(words)
        )

        chunk = " ".join(
            words[start:end]
        ).strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(words):
            break

        start = end - overlap

    return chunks


# ============================================================
# 3. PARAGRAPH-AWARE CHUNKING
# ============================================================

def chunk_by_paragraphs(
    text,
    chunk_size=DEFAULT_CHUNK_SIZE,
    overlap=DEFAULT_OVERLAP
):
    """Pack paragraphs into chunks guided by the target word limit.

    Paragraphs are combined while they fit; when a paragraph exceeds the limit,
    any pending text is emitted and that paragraph is split with
    :func:`chunk_by_words`. Overlap words from a completed chunk are carried
    into the next paragraph-based chunk to preserve context.

    Args:
        text: Normalized or raw text with paragraphs separated by newlines.
        chunk_size: Maximum target word count for a chunk.
        overlap: Trailing words retained across paragraph-based chunks and
            oversized-paragraph splits.

    Returns:
        A list of text chunks; empty or newline-only input yields an empty list.
    """

    if not text:
        return []

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n")
        if paragraph.strip()
    ]

    if not paragraphs:
        return []

    chunks = []

    current_paragraphs = []
    current_word_count = 0

    for paragraph in paragraphs:

        paragraph_word_count = len(
            paragraph.split()
        )

        # ----------------------------------------------------
        # Paragraph itself is too large
        # ----------------------------------------------------

        if paragraph_word_count > chunk_size:

            # Flush current chunk first
            if current_paragraphs:

                chunks.append(
                    " ".join(
                        current_paragraphs
                    ).strip()
                )

                current_paragraphs = []
                current_word_count = 0

            # Split large paragraph
            large_chunks = chunk_by_words(
                paragraph,
                chunk_size=chunk_size,
                overlap=overlap
            )

            chunks.extend(
                large_chunks
            )

            continue

        # ----------------------------------------------------
        # Adding paragraph would exceed chunk size
        # ----------------------------------------------------

        if (
            current_paragraphs
            and
            current_word_count
            + paragraph_word_count
            > chunk_size
        ):

            chunks.append(
                " ".join(
                    current_paragraphs
                ).strip()
            )

            # Add overlap from previous chunk
            overlap_words = []

            if overlap > 0:

                previous_words = " ".join(
                    current_paragraphs
                ).split()

                overlap_words = previous_words[
                    -overlap:
                ]

            current_paragraphs = []

            if overlap_words:

                current_paragraphs.append(
                    " ".join(overlap_words)
                )

            current_word_count = len(
                overlap_words
            )

        # Add paragraph
        current_paragraphs.append(
            paragraph
        )

        current_word_count += (
            paragraph_word_count
        )

    # Final chunk
    if current_paragraphs:

        chunks.append(
            " ".join(
                current_paragraphs
            ).strip()
        )

    return chunks


# ============================================================
# 4. MAIN GENERIC CHUNKER
# ============================================================

def chunk_generic_text(
    text,
    chunk_size=DEFAULT_CHUNK_SIZE,
    overlap=DEFAULT_OVERLAP
):
    """Normalize extracted text and return paragraph-aware structured chunks.

    This is the general-document path used for extracted text, including
    content from office documents, PDFs, plain text, and Google Docs. It
    delegates splitting to :func:`chunk_by_paragraphs`, then adds the fields
    expected by the indexing pipeline.

    Args:
        text: Document text after source-specific extraction.
        chunk_size: Maximum target number of words per chunk.
        overlap: Number of words carried across chunk boundaries.

    Returns:
        A list of dictionaries with one-based ``chunk_id``, ``section`` set to
        ``"General"``, chunk ``text``, and ``word_count``. If normalization
        leaves no text, the result is an empty list.

    The caller generates embeddings from each dictionary's ``text`` value and
    stores that same text alongside document metadata in ChromaDB.
    """

    text = normalize_text(text)

    if not text:
        return []

    chunks = chunk_by_paragraphs(
        text,
        chunk_size=chunk_size,
        overlap=overlap
    )

    structured_chunks = []

    for i, chunk in enumerate(
        chunks,
        start=1
    ):

        structured_chunks.append({
            "chunk_id": i,
            "section": "General",
            "text": chunk,
            "word_count": len(
                chunk.split()
            )
        })

    return structured_chunks
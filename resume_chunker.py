"""Detect resume-like extracted text and create section-aware retrieval chunks.

The ingestion pipeline uses the detector to choose this chunker instead of the
generic document path. Section labels are preserved in each chunk so retrieved
resume content retains its semantic context.
"""

import re


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_CHUNK_SIZE = 400       # words
DEFAULT_OVERLAP = 50           # words


# ============================================================
# COMMON RESUME SECTION HEADINGS
# ============================================================

RESUME_SECTION_HEADINGS = {
    "summary",
    "professional summary",
    "executive summary",
    "profile",
    "professional profile",
    "career summary",
    "career objective",
    "objective",

    "skills",
    "technical skills",
    "core skills",
    "key skills",
    "technical expertise",
    "areas of expertise",
    "competencies",
    "core competencies",

    "experience",
    "professional experience",
    "work experience",
    "employment history",
    "professional history",
    "career history",
    "work history",

    "education",
    "educational background",
    "academic background",
    "academic qualifications",

    "certifications",
    "certificates",
    "professional certifications",

    "projects",
    "key projects",
    "projects experience",
    "project experience",

    "achievements",
    "key achievements",
    "accomplishments",

    "awards",
    "honors",

    "publications",
    "research",

    "languages",
    "language skills",

    "interests",
    "hobbies",

    "references",
}

def is_resume_text(text):
    """Classify extracted text as resume-like using content signals.

    The text is normalized and lowercased, then checked for a fixed set of
    resume-related phrases. At least three distinct signals must be present;
    filenames and the heading-detection heuristics are not consulted.

    Args:
        text: Extracted document text.

    Returns:
        ``True`` when at least three resume signals occur, otherwise ``False``.
    """

    if not text:
        return False

    normalized_text = normalize_text(text)

    if not normalized_text:
        return False

    text_lower = normalized_text.lower()

    resume_signals = [
        "professional experience",
        "work experience",
        "employment history",
        "career history",
        "technical skills",
        "core competencies",
        "professional summary",
        "career summary",
        "education",
        "certifications",
        "projects",
        "achievements",
        "languages",
        "awards",
    ]

    matched_signals = 0

    for signal in resume_signals:
        if signal in text_lower:
            matched_signals += 1

    # Require multiple resume characteristics
    return matched_signals >= 3

# ============================================================
# 1. TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    """Clean extracted text while preserving line structure for section parsing.

    Line breaks separate candidate headings from their content, so whitespace
    is normalized line-by-line rather than flattened into a single string.

    Args:
        text: Extracted document text.

    Returns:
        Cleaned text with normalized line endings and repeated blank lines
        collapsed, or an empty string for empty input.
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

    # Clean each line independently
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
# 2. HEADING DETECTION
# ============================================================

def normalize_heading(line):
    """Lowercase a candidate heading after trimming, colon removal, and spacing."""

    line = line.strip()

    # Remove trailing colon
    line = re.sub(r":$", "", line)

    # Collapse whitespace
    line = re.sub(r"\s+", " ", line)

    return line.lower()


def is_known_section_heading(line):
    """Check a normalized line against the known resume-heading set."""

    normalized = normalize_heading(line)

    return normalized in RESUME_SECTION_HEADINGS


def looks_like_heading(line):
    """Apply the heading heuristics used to split a resume into sections.

    Known headings match case-insensitively. Other candidates must be at most
    80 characters, not end in a period, and contain at least three letters with
    an uppercase ratio of at least 75 percent.

    Args:
        line: A single normalized or raw line of document text.

    Returns:
        Whether the line is treated as a section heading.
    """

    line = line.strip()

    if not line:
        return False

    # Known heading
    if is_known_section_heading(line):
        return True

    # Very long lines are unlikely to be headings
    if len(line) > 80:
        return False

    # A sentence is unlikely to be a heading
    if line.endswith("."):
        return False

    # Check uppercase ratio
    letters = [
        char
        for char in line
        if char.isalpha()
    ]

    if len(letters) >= 3:

        uppercase_count = sum(
            1
            for char in letters
            if char.isupper()
        )

        uppercase_ratio = (
            uppercase_count / len(letters)
        )

        if uppercase_ratio >= 0.75:
            return True

    return False


# ============================================================
# 3. SPLIT RESUME INTO SEMANTIC SECTIONS
# ============================================================

def split_into_sections(text):
    """Group non-empty lines under detected headings.

    Text before the first detected heading is assigned to ``"General"``.
    Blank lines are ignored, and each emitted section contains its heading and
    newline-joined content as separate dictionary fields.

    Args:
        text: Resume text whose line breaks are still present.

    Returns:
        A list of ``{"section": heading, "content": text}`` dictionaries.
    """

    lines = text.split("\n")

    sections = []

    current_heading = "General"
    current_content = []

    for line in lines:

        line = line.strip()

        # Ignore blank lines
        if not line:
            continue

        # New section detected
        if looks_like_heading(line):

            # Save previous section
            if current_content:

                sections.append({
                    "section": current_heading,
                    "content": "\n".join(
                        current_content
                    ).strip()
                })

            current_heading = line
            current_content = []

        else:
            current_content.append(line)

    # Save final section
    if current_content:

        sections.append({
            "section": current_heading,
            "content": "\n".join(
                current_content
            ).strip()
        })

    return sections


# ============================================================
# 4. WORD-BASED CHUNKING
# ============================================================

def chunk_by_words(
    text,
    chunk_size=DEFAULT_CHUNK_SIZE,
    overlap=DEFAULT_OVERLAP
):
    """Split an oversized paragraph into word-count windows with overlap.

    This fallback is called when paragraph-aware chunking encounters a single
    paragraph larger than its target size.

    Args:
        text: Paragraph text to split.
        chunk_size: Maximum number of words in each window.
        overlap: Number of trailing words repeated in the next window.

    Returns:
        Ordered text windows; empty or whitespace-only text yields an empty list.

    Raises:
        ValueError: For non-empty text when ``overlap`` is greater than or equal
            to ``chunk_size``.
    """

    words = text.split()

    if not words:
        return []

    if overlap >= chunk_size:
        raise ValueError(
            "Overlap must be smaller than chunk size."
        )

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
# 5. PARAGRAPH-AWARE CHUNKING
# ============================================================

def chunk_by_paragraphs(
    text,
    chunk_size=DEFAULT_CHUNK_SIZE,
    overlap=DEFAULT_OVERLAP
):
    """Group paragraphs toward a word-count target while retaining overlap.

    Paragraphs are kept together where possible. A paragraph larger than the
    target is split by :func:`chunk_by_words`. When a pending chunk is emitted
    because the next paragraph would exceed the target, its trailing overlap
    words seed the next paragraph-based chunk.

    Args:
        text: Section content with paragraph boundaries represented by newlines.
        chunk_size: Target maximum number of words per chunk.
        overlap: Number of trailing words carried to a following chunk.

    Returns:
        A list of chunk strings. Empty input yields an empty list.
    """

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n")
        if paragraph.strip()
    ]

    if not paragraphs:
        return []

    chunks = []

    current_chunk = []
    current_word_count = 0

    for paragraph in paragraphs:

        paragraph_word_count = len(
            paragraph.split()
        )

        # ----------------------------------------------------
        # Paragraph itself is larger than chunk size
        # ----------------------------------------------------

        if paragraph_word_count > chunk_size:

            # Flush current chunk
            if current_chunk:

                chunks.append(
                    " ".join(
                        current_chunk
                    ).strip()
                )

                current_chunk = []
                current_word_count = 0

            # Split large paragraph
            large_chunks = chunk_by_words(
                paragraph,
                chunk_size=chunk_size,
                overlap=overlap
            )

            chunks.extend(large_chunks)

            continue

        # ----------------------------------------------------
        # Adding paragraph would exceed chunk size
        # ----------------------------------------------------

        if (
            current_chunk
            and
            current_word_count + paragraph_word_count
            > chunk_size
        ):

            chunks.append(
                " ".join(
                    current_chunk
                ).strip()
            )

            # Create small overlap from previous chunk
            overlap_words = []

            if overlap > 0:

                previous_words = " ".join(
                    current_chunk
                ).split()

                overlap_words = previous_words[
                    -overlap:
                ]

            current_chunk = []

            if overlap_words:
                current_chunk.append(
                    " ".join(overlap_words)
                )

            current_word_count = len(
                overlap_words
            )

        # Add paragraph
        current_chunk.append(paragraph)

        current_word_count += paragraph_word_count

    # Add final chunk
    if current_chunk:

        chunks.append(
            " ".join(
                current_chunk
            ).strip()
        )

    return chunks


# ============================================================
# 6. MAIN SEMANTIC RESUME CHUNKER
# ============================================================

def chunk_resume(
    text,
    chunk_size=DEFAULT_CHUNK_SIZE,
    overlap=DEFAULT_OVERLAP
):
    """Normalize a resume, split it by section, and structure its chunks.

    Sections at or below ``chunk_size`` remain intact; larger sections use
    paragraph-aware chunking. Every emitted chunk is prefixed with its section
    label, and chunk IDs increase across the complete resume.

    Args:
        text: Extracted resume text.
        chunk_size: Maximum target number of words per chunk.
        overlap: Number of words carried across paragraph-based chunk boundaries.

    Returns:
        A list of dictionaries containing one-based ``chunk_id``, ``section``,
        labeled chunk ``text``, and ``word_count``. Empty normalized input
        yields an empty list.
    """

    text = normalize_text(text)

    if not text:
        return []

    sections = split_into_sections(text)

    chunks = []

    chunk_number = 0

    for section in sections:

        section_name = section["section"]

        section_content = section["content"]

        word_count = len(
            section_content.split()
        )

        # ----------------------------------------------------
        # Small section
        # ----------------------------------------------------

        if word_count <= chunk_size:

            chunk_number += 1

            chunks.append({
                "chunk_id": chunk_number,
                "section": section_name,
                "text": (
                    f"Section: {section_name}\n\n"
                    f"{section_content}"
                ),
                "word_count": word_count
            })

            continue

        # ----------------------------------------------------
        # Large section
        # ----------------------------------------------------

        section_chunks = chunk_by_paragraphs(
            section_content,
            chunk_size=chunk_size,
            overlap=overlap
        )

        for section_chunk in section_chunks:

            chunk_number += 1

            chunks.append({
                "chunk_id": chunk_number,
                "section": section_name,
                "text": (
                    f"Section: {section_name}\n\n"
                    f"{section_chunk}"
                ),
                "word_count": len(
                    section_chunk.split()
                )
            })

    return chunks


# ============================================================
# 7. RAG PIPELINE ENTRY POINT
# ============================================================

def chunk_resume_text(
    text,
    chunk_size=DEFAULT_CHUNK_SIZE,
    overlap=DEFAULT_OVERLAP
):
    """Expose resume chunking to the document-ingestion pipeline.

    The caller has already extracted document text and selected this route
    using :func:`is_resume_text`; this function delegates chunk construction
    to :func:`chunk_resume` without changing the chunk records.

    Args:
        text: Extracted resume text.
        chunk_size: Maximum target number of words per chunk.
        overlap: Number of words carried across paragraph-based chunk boundaries.

    Returns:
        The structured resume chunks returned by :func:`chunk_resume`.
    """

    return chunk_resume(
        text,
        chunk_size=chunk_size,
        overlap=overlap
    )
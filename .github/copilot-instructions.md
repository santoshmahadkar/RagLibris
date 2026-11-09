# RagLibris Code Documentation Instructions

## Primary objective

When asked to document or comment code in this project:

1. Inspect the code before adding comments.
2. Understand the purpose and flow of each function, class, and major code section.
3. Add comments based on the actual implementation.
4. Do not change application logic, variable names, function names, or behavior.
5. Do not refactor the code unless explicitly requested.
6. Do not add comments that merely repeat what the code obviously says.

## Commenting strategy

Add comments at meaningful logical boundaries.

For each major section of code, explain:

- What the section does
- Why the section exists
- Important processing logic
- Important dependencies or external services
- Important assumptions
- Important error-handling behavior
- Important data transformations

Use comments for concepts that help a developer understand the architecture and reasoning.

Avoid excessive comments on simple statements.

## Functions

For important functions, add a concise docstring explaining:

- Purpose
- Parameters
- Return value
- Important side effects
- Exceptions, where relevant

Example:

def chunk_generic_text(text, chunk_size=1000, overlap=100):
    """
    Splits a document into overlapping text chunks.

    Args:
        text: Normalized document text.
        chunk_size: Maximum number of words per chunk.
        overlap: Number of words shared between consecutive chunks.

    Returns:
        A list of structured chunk dictionaries.
    """

## Major sections

Use section comments such as:

# ---------------------------------------------------------
# Document Processing
# ---------------------------------------------------------

when a file contains multiple major processing stages.

For smaller sections use:

# Normalize document text
# Detect document type
# Generate embeddings
# Store chunks in ChromaDB

## RAG-specific documentation

When documenting RagLibris, clearly explain the flow between:

Document
→ Text Extraction
→ Document Type Detection
→ Chunking
→ Embedding
→ ChromaDB
→ Retrieval
→ Context Construction
→ LLM
→ Response

Explain the purpose of each stage where it appears in the code.

## Google Drive code

For Google Drive related code, explain:

- Authentication
- OAuth credentials
- token reuse
- Drive API calls
- File metadata
- Incremental processing
- New files
- Modified files
- Unchanged files
- Deleted files

Do not expose secrets, tokens, API keys, or credentials in comments.

## Embedding code

Explain:

- Which embedding model is being used
- What text is being embedded
- Why embeddings are generated
- Where embeddings are stored
- How embeddings are later used for retrieval

## ChromaDB code

Explain:

- Collection creation/access
- Document IDs
- Metadata
- Embeddings
- Insert/update/delete operations
- Similarity retrieval

## Comments must be implementation-aware

Do not make assumptions about code.

If the implementation is unclear:

1. Inspect related functions/files.
2. Trace how the value is produced and consumed.
3. Only then write the comment.

If something cannot be determined from the code, do not invent an explanation.

## Important

DO NOT:

- Change code logic
- Rename variables
- Reformat unrelated code
- Change imports unnecessarily
- Introduce new dependencies
- Rewrite functions
- Add unnecessary comments
- Add comments that state the obvious

The task is documentation only unless explicitly instructed otherwise.

## Documentation style

Write comments for a developer who understands Python and AI/ML but is learning this project.

Comments should explain the "why" and important "how", not simply translate Python syntax into English.

Prefer:

# Remove existing chunks before re-indexing a modified document
# to prevent stale embeddings from remaining in ChromaDB.

Instead of:

# Delete chunks
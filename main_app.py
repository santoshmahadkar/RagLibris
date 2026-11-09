"""Query-time RAG pipeline for answering questions from indexed documents.

At import time this module opens the existing persistent ChromaDB collection.
For each question, it creates local Ollama embeddings, retrieves stored chunks,
builds source-linked context, and asks Groq to produce the answer.
"""

import ollama
import chromadb
from dotenv import load_dotenv
from groq import Groq
import os
# from chunk_engine import chunk_text

load_dotenv()

DB_PATH = os.getenv("DB_PATH")

# The indexer creates this persistent collection; retrieval expects it to exist.
client = chromadb.PersistentClient(
    path=DB_PATH
)
collection = client.get_collection(name="google_drive_files")

# The question is divided by characters here; the indexed documents use the
# separate word- and paragraph-aware chunker in generic_chunker.py.
def chunk_text(text, chunk_size=1000, overlap=100):
    """Split text into fixed-width character slices with a shared boundary.

    Args:
        text: Input text to divide.
        chunk_size: Maximum number of characters per slice.
        overlap: Number of trailing characters repeated in the next slice.

    Returns:
        The character slices in their original order.

    Assumes ``chunk_size`` is greater than ``overlap``; the inputs are not
    validated here.
    """

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks

def core_app(user_question):
    """Retrieve document context and generate an answer for a user question.

    The question is embedded with Ollama's ``all-minilm:latest`` model. Those
    vectors query the existing ``google_drive_files`` ChromaDB collection;
    result metadata supplies ``file_id`` for candidate filtering and
    ``file_name``/``web_view_link`` for the context sent to Groq's
    ``openai/gpt-oss-120b`` chat model.

    Args:
        user_question: The question to answer using the indexed documents.

    Returns:
        The generated answer text from the first Groq choice.

    Side effects:
        Prints pipeline progress, retrieved identifiers, context, and answer.

    Exceptions from Ollama, ChromaDB, or Groq are not caught here and propagate
    to the caller.
    """

    embeddings = []

    # Embed the query text locally using the same model family used by the indexer.
    print("#" * 80)
    print(f"STEP #1")
    print("#" * 80)
    print(f"--> Sending user question to embedding model for embedding generation")
    print("-" * 60)

    chunks = chunk_text(user_question.strip(), chunk_size=1000, overlap=100)

    print("#" * 80)
    print(f"STEP #2")
    print("#" * 80)
    print(f"--> creating embedding for the user question")
    print("-" * 60)

    response = ollama.embed(
        model="all-minilm:latest",
        input=chunks
    )

    embeddings = response.embeddings

    # Search by vector similarity, then use file IDs from the first query-result
    # group to constrain a second retrieval to those candidate documents.
    print(f"--> These are the number of embeddings for the user question")
    print("-" * 60)

    print(f"Embeddings: {len(embeddings)}")

    print("#" * 80)
    print(f"STEP #3")
    print("#" * 80)
    print(f"--> Querying the collection with the embeddings of user questionto get the top 3 results for each embedding.")
    print("-" * 60)

    results = collection.query(
            query_embeddings=embeddings,
            n_results=20*len(embeddings),
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

    print(f"--> These are the number of results for the user question")
    print("-" * 60)

    print(f"Results: {len(results['documents'][0])}")

    # Candidate selection reads the first result group and deduplicates its file IDs.
    print("#" * 80)
    print(f"STEP #4")
    print("#" * 80)
    print(f"--> Fetching all file_ids from the results and get the unique file_ids to avoid duplicate file_ids in the context.")
    print("-" * 60)

    file_ids = []

    for i in range(len(results["documents"][0])):
        metadata = results["metadatas"][0][i]
        file_id = metadata["file_id"]
        file_ids.append(file_id)

    print(f"file ids before finding unique : {file_ids}")

    file_ids = list(set(file_ids))

    print(f"--> These are the number of unique file_ids for the user question")
    print("-" * 60)

    print(f"File IDs: {file_ids}")
    print("*" * 60)

    print("#" * 80)
    print(f"STEP #5")
    print("#" * 80)
    print(f"--> Querying the collection with the unique file_ids to get the top 1 result for each file_id.")
    print("-" * 60)
    new_results = collection.query(
        query_embeddings=embeddings,
        n_results=3*len(embeddings),
        include=[
            "documents",
            "metadatas",
            "distances"
        ],
        where={
            "file_id": {"$in": file_ids}
        }
    )

    print(f"Number of file_ids: {len(file_id)}")

    print(new_results['documents'][0][0])
    print()
    print(new_results['documents'][0][1])
    print()
    print(new_results['documents'][0][2])

    print(f"--> These are the number of new results for the user question")
    print("-" * 60)

    print(f"New Results count: {len(new_results['documents'])}")
    
    # Build prompt context from the second query's first result group. The indexer
    # stores these metadata keys with each chunk for source attribution.
    print("#" * 80)
    print(f"STEP #6")
    print("#" * 80)
    print(f"--> Creating context from the new results to send it to the model for response.")
    print("-" * 60)

    context = []

    for i in range(len(new_results["documents"][0])):
        # retrived_chunk = new_results["documents"][0][i]
        metadata = new_results["metadatas"][0][i]
        context_dict = {}
        context_dict["file_name"] = metadata['file_name']
        context_dict["contents"] = new_results['documents'][0][i]
        context_dict["weblink"] = metadata['web_view_link']
        context.append(context_dict)

    print(f"Context: {context}")
    print(len(context))

    client = Groq()

    model = "openai/gpt-oss-120b"

    response = client.chat.completions.create(
        model=model,
        messages=[
        {
                "role": "user", 
                "content": f"""Answer the following question: {user_question} based on the following \
                context: {context} and give me the 'weblink' of that candidate from the context. \
                If not available, just answer the question based on the context.
                Answer should be in the following format:
                Answer: Candidate XYZ is the best fit for power BI because he is having 5 years of experience in power BI and has worked on multiple projects.  
                weblink: https://docs.google.com/document/d/1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7/edit
                """
            }
        ],
        temperature=0.3
    )
    answer = response.choices[0].message.content
    print(f"This is the answer \n: {answer}")
    return answer
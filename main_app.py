"""Query-time RAG pipeline for answering questions from indexed documents.

At import time this module opens the existing persistent ChromaDB collection.
For each question, it creates local Ollama embeddings, retrieves stored chunks,
builds source-linked context, and asks Groq to produce the answer.
"""

import ollama
import chromadb
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI
import os
from collections import defaultdict
import tiktoken
from sentence_transformers import CrossEncoder

load_dotenv()

DB_PATH = os.getenv("DB_PATH")

# The indexer creates this persistent collection; retrieval expects it to exist.
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_collection(name="google_drive_files")

reranker = CrossEncoder("BAAI/bge-reranker-base")

def rerank_results(user_question, results, top_n=20):

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    pairs = [
        [user_question, document]
        for document in documents
    ]

    scores = reranker.predict(pairs)

    ranked_results = []

    for document, metadata, score in zip(
        documents,
        metadatas,
        scores
    ):
        ranked_results.append({
            "file_id": metadata.get("file_id"),
            "file_name": metadata.get("file_name"),
            "document": document,
            "rerank_score": float(score)
        })

    ranked_results.sort(
        key=lambda x: x["rerank_score"],
        reverse=True
    )

    return ranked_results[:top_n]

def count_tokens(text):
    """
    Estimate the number of tokens in a text string.

    Uses the o200k_base tokenizer as a practical approximation
    for modern OpenAI-compatible models.
    """

    encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text))


def limit_context_by_tokens(reranked_results, max_tokens=2500):
    """
    Limit the total context sent to the LLM based on token count.

    Input:
    [
        {
            "file_id": "...",
            "file_name": "...",
            "document": "...",
            "rerank_score": 0.95
        }
    ]

    Output:
    [
        {
            "file_id": "...",
            "file_name": "...",
            "contents": "...",
            "rerank_score": 0.95
        }
    ]
    """

    limited_context = []
    total_tokens = 0
    original_tokens = 0

    # Calculate original token count
    for result in reranked_results:
        content = result.get("document", "")

        if not content:
            continue

        original_tokens += count_tokens(content)

    # Select content until token limit is reached
    for result in reranked_results:

        content = result.get("document", "")

        if not content:
            continue

        remaining_tokens = max_tokens - total_tokens

        if remaining_tokens <= 0:
            break

        content_tokens = count_tokens(content)

        # Entire chunk fits
        if content_tokens <= remaining_tokens:

            selected_content = content

        # Only part of chunk fits
        else:

            encoding = tiktoken.get_encoding("o200k_base")

            token_ids = encoding.encode(content)

            selected_token_ids = token_ids[:remaining_tokens]

            selected_content = encoding.decode(
                selected_token_ids
            )

        selected_tokens = count_tokens(selected_content)

        limited_record = {
            "file_id": result.get("file_id"),
            "file_name": result.get("file_name"),
            "contents": selected_content,
            "rerank_score": result.get("rerank_score")
        }

        limited_context.append(limited_record)

        total_tokens += selected_tokens

    print(f"Original context tokens: {original_tokens}")
    print(f"Limited context tokens: {total_tokens}")
    print(f"Token limit: {max_tokens}")

    return limited_context


def group_chromadb_results(results):

    print()
    print()
    print()
    print(results)
    print()
    print()
    print()

    grouped = {}

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    for document, metadata in zip(documents, metadatas):

        print(f"here is the extracted metadata: {metadata}")
        file_id = metadata.get("file_id")
        #weblink = metadata.get("web_view_link")

        key = (file_id) #, weblink)

        if key not in grouped:

            grouped[key] = {
                "file_id": file_id,
                "file_name": metadata.get("file_name"),
                #"weblink": weblink,
                "contents": []
            }

        grouped[key]["contents"].append(document)

    for record in grouped.values():

        record["contents"] = "\n\n".join(record["contents"])

    return list(grouped.values())

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
    print("=" * 80)
    print(f"STEP #1")
    print("=" * 80)
    print(f"--> Sending user question to embedding model for embedding generation")
    print("=" * 80)

    chunks = chunk_text(user_question.strip(), chunk_size=1000, overlap=100)

    print("=" * 80)
    print(f"STEP #2")
    print("=" * 80)
    print(f"--> creating embedding for the user question")
    print("=" * 80)

    response = ollama.embed(
        model="all-minilm:latest",
        input=chunks
    )

    q_embeddings = response.embeddings

    # Search by vector similarity, then use file IDs from the first query-result
    # group to constrain a second retrieval to those candidate documents.
    print(f"--> These are the number of embeddings for the user question")
    print("=" * 80)

    print(f"Embeddings: {len(q_embeddings)}")

    print("=" * 80)
    print(f"STEP #3")
    print("=" * 80)
    print(f"--> Querying the collection with the embeddings of user questionto get the top 3 results for each embedding.")
    print("=" * 80)

    # ChromaDB retrieval
    results = collection.query(
        query_embeddings=q_embeddings,
        n_results=50,
        include=["documents", "metadatas", "distances"]
    )

    print(f"--> These are the number of results for the user question")
    print("=" * 80)

    print(f"Results: {len(results['documents'][0])}")

    # # Candidate selection reads the first result group and deduplicates its file IDs.
    # print("=" * 80)
    # print(f"STEP #4")
    # print("=" * 80)
    # print(f"--> Fetching all file_ids from the results and get the unique file_ids to avoid duplicate file_ids in the context.")
    # print("=" * 80)

    # file_ids = []

    # for i in range(len(results["documents"][0])):
    #     metadata = results["metadatas"][0][i]
    #     file_id = metadata["file_id"]
    #     file_ids.append(file_id)

    # print(f"file ids before finding unique : {file_ids}")

    # file_ids = list(set(file_ids))

    # print(f"--> These are the number of unique file_ids for the user question")
    # print("=" * 80)

    # print(f"File IDs: {file_ids}")
    # print("*" * 60)

    # print("=" * 80)
    # print(f"STEP #5")
    # print("=" * 80)
    # print(f"--> Querying the collection with the unique file_ids to get the top 1 result for each file_id.")
    # print("=" * 80)
    # new_results = collection.query(
    #     query_embeddings=q_embeddings,
    #     n_results=20*len(q_embeddings),
    #     include=[
    #         "documents",
    #         "metadatas",
    #         "distances"
    #     ],
    #     where={
    #         "file_id": {"$in": file_ids}
    #     }
    # )

    # Rerank retrieved chunks
    reranked_results = rerank_results(
        user_question,
        results,
        top_n=20
    )


    print("\nRERANKED RESULTS")
    print("=" * 80)

    for rank, result in enumerate(reranked_results, start=1):
        print(f"Rank       : {rank}")
        print(f"File ID    : {result['file_id']}")
        print(f"File Name  : {result['file_name']}")
        print(f"Score      : {result['rerank_score']}")
        print(f"Document   : {result['document'][:500]}")
        print("-" * 80)

    
    # grouped_records = group_chromadb_results(new_results)    
    # grouped_records = group_chromadb_results(rerank_results)


    # print(f"--> These are the number of new results for the user question")
    # print("=" * 80)
    # print(f"Number of grouped records: {len(grouped_records)}")

    # print(f"New Results count: {len(grouped_records['documents'])}")
    
    # Build prompt context from the second query's first result group. The indexer
    # stores these metadata keys with each chunk for source attribution.
    print("=" * 80)
    print(f"STEP #6")
    print("=" * 80)
    print(f"--> Creating context from the new results to send it to the model for response.")
    print("=" * 80)

    # context = grouped_records
    # Limit context to 2500 tokens
    context = limit_context_by_tokens(
        reranked_results,
        max_tokens=2500
    )

    print(f"Context: {context}")
    print(len(context))

    # client = OpenAI(
    #         base_url="http://localhost:11434/v1",
    #         api_key="ollama"
    #     )

    # model = "lfm2.5-thinking:latest"
    
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY")
    )

    model = "openai/gpt-oss-120b"
    

    response = client.chat.completions.create(
        model=model,
        messages=[
        {
                "role": "user", 
                "content": f"""Answer the following question: {user_question} based on the following \
                context: {context} and give me the 'file_id' of that candidate from the context. \
                If not available, just answer the question based on the context. Do not invest any of facts, like file_id, etc
                Answer should be in the following format:
                Answer: Candidate XYZ is the best fit for power BI because he is having 5 years of experience in power BI and has worked on multiple projects.  
                weblink: FILE_ID_<file_id>
                Score: should be in % style out of 100
                output should be in tabular format and ranked as per score and output columns should be "rank" "Candidate Name", "Summary Skills" "Skills Keywords" "Score" "Weblink"
                """
            }
        ],
        temperature=0.3
    )
    answer = response.choices[0].message.content
    print(f"This is the answer \n: {answer}")
    return answer
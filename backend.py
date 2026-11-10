"""FastAPI entry point for the question-answering API.

The HTTP layer validates request and response shapes, then delegates question
processing to ``main_app.core_app``. RAG services and model calls are managed
by that function rather than by these route handlers.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from main_app import core_app
import re
import chromadb
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH= os.getenv("DB_PATH")

client = chromadb.PersistentClient(
    path=DB_PATH
)
collection = client.get_collection(name="google_drive_files")

app = FastAPI(
    title="RAG Backend API",
    description="Backend API for RAG chatbot",
    version="1.0.0"
)


# --------------------------------------------------
# Request model
# --------------------------------------------------

class QuestionRequest(BaseModel):
    """Validated request body containing the user's question."""

    question: str


# --------------------------------------------------
# Response model
# --------------------------------------------------

class AnswerResponse(BaseModel):
    """Response body returned by the question endpoint."""

    answer: str

def get_web_links_by_file_ids(collection, file_ids):
    """
    Look up web_view_link for file IDs in ChromaDB.
    """

    if not file_ids:
        return {}

    results = collection.get(
        where={
            "file_id": {
                "$in": file_ids
            }
        },
        include=["metadatas"]
    )

    web_links = {}

    for metadata in results.get("metadatas", []):

        file_id = metadata.get("file_id")
        web_view_link = metadata.get("web_view_link")

        if file_id and web_view_link:

            # Add FILE_ID_ prefix because that's
            # what the LLM response contains.
            llm_file_id = f"FILE_ID_{file_id}"

            web_links[llm_file_id] = web_view_link

    return web_links

def replace_file_ids_with_links(text, web_links):

    def replace_match(match):

        file_id = match.group(0)

        return web_links.get(file_id, file_id)

    return re.sub(
        r'FILE_ID_[A-Za-z0-9_-]+',
        replace_match,
        text
    )


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
def health_check():
    """Return a simple liveness response without checking downstream services."""

    return {
        "status": "UP"
    }


# --------------------------------------------------
# Ask question
# --------------------------------------------------

@app.post("/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest):

    question = request.question

    print("Question received:")
    print(question)

    # Run RAG pipeline
    llm_response = core_app(question)

    print("====================================")
    print("LLM RESPONSE:")
    print(llm_response)

    # --------------------------------------------------
    # Extract FILE_ID_* references from LLM response
    # --------------------------------------------------

    file_ids_from_llm = re.findall(
        r'FILE_ID_[A-Za-z0-9_-]+',
        llm_response
    )

    # Remove duplicates while preserving order
    file_ids_from_llm = list(
        dict.fromkeys(file_ids_from_llm)
    )

    print("FILE IDs FROM LLM:")
    print(file_ids_from_llm)

    # --------------------------------------------------
    # Convert FILE_ID_* → actual ChromaDB file_id
    # --------------------------------------------------

    chromadb_file_ids = [
        file_id.removeprefix("FILE_ID_")
        for file_id in file_ids_from_llm
    ]

    print("FILE IDs USED FOR CHROMADB:")
    print(chromadb_file_ids)

    # --------------------------------------------------
    # Retrieve web links
    # --------------------------------------------------

    web_links = get_web_links_by_file_ids(
        collection,
        chromadb_file_ids
    )

    print("WEB LINKS FOUND:")
    print(web_links)

    # --------------------------------------------------
    # Replace FILE_ID_* with actual web link
    # --------------------------------------------------

    answer = replace_file_ids_with_links(
        llm_response,
        web_links
    )

    print("====================================")
    print("FINAL ANSWER:")
    print(answer)
    print("====================================")

    return {
        "answer": answer
    }
"""FastAPI entry point for the question-answering API.

The HTTP layer validates request and response shapes, then delegates question
processing to ``main_app.core_app``. RAG services and model calls are managed
by that function rather than by these route handlers.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from main_app import core_app

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
    """Pass a validated question to the RAG pipeline and return its answer.

    The question is also written to standard output for request visibility.
    Exceptions from ``core_app`` are not caught here, so FastAPI handles them
    as request failures.
    """

    question = request.question

    print("Question received:")
    print(question)

    # The pipeline result replaces this placeholder before it is returned.
    answer = f"""
    I received your question:

    {question}

    RAG processing will happen here.
    """
    # Embedding, retrieval, context construction, and generation are handled by core_app.
    answer = core_app(question)

    return {
        "answer": answer
    }
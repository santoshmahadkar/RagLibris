"""Streamlit chat interface that sends questions to the local FastAPI service.

Conversation messages live in Streamlit session state; the frontend does not
perform retrieval or model inference itself.
"""

import streamlit as st
import requests
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# The displayed name is supplied through the environment, typically via .env.
USER_NAME = os.getenv("USER_NAME")

# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="My RAG Assistant",
    page_icon="🤖",
    layout="wide"
)

# --------------------------------------------------
# Configuration
# --------------------------------------------------

# Questions are posted to the separately running backend, which owns the RAG flow.
BACKEND_URL = "http://localhost:8000/ask"

# --------------------------------------------------
# Session state
# --------------------------------------------------

# Streamlit reruns this script after interactions, so keep the transcript in session state.
if "messages" not in st.session_state:
    st.session_state.messages = []


# --------------------------------------------------
# Time-based greeting
# --------------------------------------------------

def get_greeting():
    """Choose a greeting from the machine's current local hour.

    Returns:
        The greeting text for the current time period.
    """

    current_hour = datetime.now().hour

    if 5 <= current_hour < 12:
        return "Good Morning 🌅"

    elif 12 <= current_hour < 17:
        return "Good Afternoon ☀️"

    elif 17 <= current_hour < 21:
        return "Good Evening 🌇"

    else:
        return "Good Night 🌙"


# --------------------------------------------------
# Header
# --------------------------------------------------

greeting = get_greeting()

st.title(f"{greeting}, {USER_NAME} 👋")

st.markdown(
    "### How can I help you today?"
)

st.divider()


# --------------------------------------------------
# Display previous conversation
# --------------------------------------------------

# Re-render the saved transcript on each Streamlit script rerun.
for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# --------------------------------------------------
# Chat input
# --------------------------------------------------

user_question = st.chat_input(
    "Type your question here..."
)


# --------------------------------------------------
# Submit question
# --------------------------------------------------

if user_question:

    # Display user's question
    st.session_state.messages.append({
        "role": "user",
        "content": user_question
    })

    with st.chat_message("user"):
        st.markdown(user_question)

    # The backend returns the generated answer; request and unexpected failures
    # are shown in the chat and saved as the assistant's response for this turn.
    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            try:

                response = requests.post(
                    BACKEND_URL,
                    json={
                        "question": user_question
                    },
                    timeout=120
                )

                response.raise_for_status()

                data = response.json()

                answer = data["answer"]

            except requests.exceptions.RequestException as e:

                answer = f"Backend error: {e}"

            except Exception as e:

                answer = f"Unexpected error: {e}"

        st.markdown(answer)

    # Save assistant response
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })
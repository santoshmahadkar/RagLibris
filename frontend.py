"""
Streamlit chat interface that sends questions to the local FastAPI service.

Conversation messages live in Streamlit session state; the frontend does not
perform retrieval or model inference itself.
"""

import streamlit as st
import requests
from dotenv import load_dotenv
import os
import subprocess
import time
from datetime import datetime


load_dotenv()


# --------------------------------------------------
# Configuration
# --------------------------------------------------

# The displayed name is supplied through the environment, typically via .env.
USER_NAME = os.getenv("USER_NAME")

# Questions are posted to the separately running backend,
# which owns the RAG flow.
BACKEND_URL = "http://localhost:8000/ask"

# Backend shutdown endpoint.
SHUTDOWN_URL = "http://localhost:8000/shutdown"


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="My RAG Assistant",
    page_icon="🤖",
    layout="wide"
)


# --------------------------------------------------
# Session state
# --------------------------------------------------

# Streamlit reruns this script after interactions,
# so keep the transcript in session state.
if "messages" not in st.session_state:
    st.session_state.messages = []


# --------------------------------------------------
# Time-based greeting
# --------------------------------------------------

def get_greeting():
    """
    Choose a greeting from the machine's current local hour.

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


# Generate the greeting
greeting = get_greeting()


# --------------------------------------------------
# Header / Top Banner
# --------------------------------------------------

col1, col2 = st.columns([8, 1])

with col1:
    st.title(f"{greeting}, {USER_NAME} 👋")

with col2:
    st.write("")
    st.write("")

    if st.button(
        "⏻ Close",
        type="secondary",
        use_container_width=True
    ):

        try:
            # Ask backend for its process ID.
            response = requests.post(
                SHUTDOWN_URL,
                timeout=2
            )

            response.raise_for_status()

            backend_pid = response.json().get("pid")

            # Kill the FastAPI process and its child processes.
            if backend_pid:

                subprocess.Popen(
                    [
                        "taskkill",
                        "/PID",
                        str(backend_pid),
                        "/T",
                        "/F"
                    ],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

        except Exception:
            # Backend may already be stopped.
            pass

        # Inform the user before terminating Streamlit.
        st.warning("Closing RagLibris...")

        time.sleep(0.5)

        # Stop Streamlit frontend.
        os._exit(0)


st.markdown("### How can I help you today?")
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

    # --------------------------------------------------
    # Display user's question
    # --------------------------------------------------

    st.session_state.messages.append({
        "role": "user",
        "content": user_question
    })

    with st.chat_message("user"):
        st.markdown(user_question)


    # --------------------------------------------------
    # Get answer from backend
    # --------------------------------------------------

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


        # Display answer
        st.markdown(answer)


    # --------------------------------------------------
    # Save assistant response
    # --------------------------------------------------

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })
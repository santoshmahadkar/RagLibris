# 🤖 RagLibris — AI Document Assistant


RagLibris is an AI-powered document question-answering system built using **Retrieval-Augmented Generation (RAG)**.


It allows users to ask natural-language questions about their documents and retrieves relevant information from a local vector database before generating an answer using an LLM.


The project was developed as part of my **AI/ML learning and hands-on training journey** to demonstrate practical implementation of RAG, embeddings, vector databases, document processing, API development, and AI application development.


---


## 🚀 Key Capabilities


- Document ingestion and text extraction

- Resume-aware document chunking

- Generic document chunking

- Semantic embeddings using a local embedding model

- Vector storage and similarity search using ChromaDB

- Retrieval-Augmented Generation (RAG)

- LLM-based response generation

- FastAPI backend

- Streamlit frontend

- Google Drive document ingestion

- Incremental vector database updates

- Local embedding generation using Ollama

- Environment-based configuration

- Windows single-click application launcher


---


## 🏗️ Architecture


```text

                         ┌──────────────────────┐

                         │      User            │

                         │  Natural Language    │

                         │      Question        │

                         └──────────┬───────────┘

                                    │

                                    ▼

                         ┌──────────────────────┐

                         │   Streamlit UI       │

                         │      frontend.py     │

                         └──────────┬───────────┘

                                    │

                              HTTP Request

                                    │

                                    ▼

                         ┌──────────────────────┐

                         │   FastAPI Backend    │

                         │      backend.py      │

                         └──────────┬───────────┘

                                    │

                                    ▼

                         ┌──────────────────────┐

                         │   RAG Pipeline       │

                         └──────────┬───────────┘

                                    │

                         Query Embedding

                                    │

                                    ▼

                         ┌──────────────────────┐

                         │      ChromaDB        │

                         │   Vector Database    │

                         └──────────┬───────────┘

                                    │

                          Relevant Documents

                                    │

                                    ▼

                         ┌──────────────────────┐

                         │      Context         │

                         └──────────┬───────────┘

                                    │

                                    ▼

                         ┌──────────────────────┐

                         │        LLM           │

                         │   Response Generation│

                         └──────────┬───────────┘

                                    │

                                    ▼

                         ┌──────────────────────┐

                         │    Streamlit UI      │

                         │   Generated Answer   │

                         └──────────────────────┘

```


---


## 📄 Document Processing Pipeline


Documents are processed through the following pipeline:


```text

Document

   │

   ▼

Text Extraction

   │

   ▼

Document Type Detection

   │

   ├───────────────┐

   │               │

   ▼               ▼

Resume          General

   │               │

   ▼               ▼

Resume          Generic

Chunker         Chunker

   │               │

   └───────┬───────┘

           ▼

      Text Chunks

           │

           ▼

      Embeddings

           │

           ▼

       ChromaDB

```


### Resume-aware Chunking


Resumes are semi-structured documents, so RagLibris uses structure-aware chunking based on sections such as:


- Professional Summary

- Professional Experience

- Technical Skills

- Education

- Certifications

- Projects

- Achievements


### Generic Document Chunking


Non-resume documents use a generic paragraph/word-based chunking strategy with configurable chunk size and overlap.


---


## 🧠 AI/ML Components


### Embedding Model


RagLibris uses a locally hosted embedding model through **Ollama**.


Current embedding model:


```text

all-minilm:latest

```


The embedding model converts text chunks into numerical vectors that represent their semantic meaning.


---


## 🔎 Vector Database


The project uses **ChromaDB** as the local vector database.


Each document chunk is stored with:


- Document ID

- Source file ID

- File name

- Section

- Chunk number

- Word count

- Original chunk text

- Embedding vector


This metadata allows retrieved information to be traced back to its source document.


---


## 🔄 Incremental Document Processing


RagLibris does not need to rebuild the entire vector database every time documents are processed.


The ingestion pipeline identifies:


### New files


```text

Drive file exists

        +

File not present in ChromaDB

        ↓

Chunk → Embed → Store

```


### Modified files


```text

File exists in ChromaDB

        +

Modified time or size changed

        ↓

Delete old chunks

        ↓

Re-chunk

        ↓

Re-embed

        ↓

Store new vectors

```


### Unchanged files


```text

File exists

        +

Modified time unchanged

        +

Size unchanged

        ↓

Skip

```


### Deleted files


```text

File exists in ChromaDB

        +

File no longer exists in source

        ↓

Delete from ChromaDB

```


This makes the ingestion process more efficient for larger document collections.


---


## 🛠️ Technology Stack


| Area | Technology |

|---|---|

| Programming | Python |

| Frontend | Streamlit |

| Backend API | FastAPI |

| API Server | Uvicorn |

| Embeddings | Ollama / all-MiniLM |

| Vector Database | ChromaDB |

| LLM | Groq |

| Document Processing | Python document/PDF libraries |

| Source Documents | Google Drive |

| Configuration | python-dotenv |

| Version Control | Git / GitHub |


---


## 📁 Project Structure


```text

RagLibris/

│

├── backend.py

├── frontend.py

├── main_app.py

│

├── offline_vector_pipeline.py

│

├── chunk_engine.py

├── generic_chunker.py

├── resume_chunker.py

│

├── embedding_testing.py

│

├── requirements.txt

├── .env.example

├── .gitignore

├── README.md

│

└── start_RagLibris.bat

```


Sensitive files and generated runtime data are intentionally excluded from the repository.


---


**## 🔐 Google Drive OAuth Authentication Setup

RagLibris uses the Google Drive API to discover and read documents stored in Google Drive. Authentication is implemented using Google's OAuth 2.0 desktop application flow.

### Authentication Flow

```text
                    Google Cloud
                         │
                         ▼
                OAuth Client ID
                         │
                         ▼
                 credentials.json
                         │
                         ▼
                   RagLibris
                         │
                         ▼
              InstalledAppFlow
                         │
                         ▼
                  Browser Login
                         │
                         ▼
                 User Consent
                         │
                         ▼
                Google Authorization
                         │
                         ▼
                    token.json
                         │
                         ▼
                 Google Drive API
```

### Prerequisites

You need:

- A Google account
- A Google Cloud project
- Google Drive API enabled
- An OAuth 2.0 Desktop Application client
- Python 3.x
- RagLibris virtual environment

### Step 1 — Create a Google Cloud Project

Open the [Google Cloud Console](https://console.cloud.google.com/) and create a new project.

Example project name:

```text
RagLibris
```

Select the project after creating it.

### Step 2 — Enable Google Drive API

Navigate to:

```text
APIs & Services
    → Library
    → Google Drive API
```

Click **Enable**.

### Step 3 — Configure OAuth

Open:

```text
Google Auth Platform
```

Configure the application under the appropriate Branding and Audience settings.

Provide:

```text
Application name: RagLibris
Support email: <your Google account>
Developer contact: <your email>
```

### Step 4 — Create OAuth Client

Navigate to:

```text
Google Auth Platform
    → Clients
    → Create Client
```

Select:

```text
Application type: Desktop app
```

Give the client a name such as:

```text
RagLibris Desktop Client
```

Click **Create**.

### Step 5 — Download credentials.json

Download the OAuth client JSON file and rename it:

```text
credentials.json
```

Place it in the RagLibris project root:

```text
RagLibris/
├── credentials.json
├── backend.py
├── frontend.py
└── ...
```

### Step 6 — Configure the Drive Scope

RagLibris uses a Google Drive OAuth scope to determine the level of access requested.

For read-only Drive access:

```python
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly"
]
```

Use the least-privileged scope required by the application.

### Step 7 — Install Google API Dependencies

Activate the RagLibris virtual environment and run:

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Step 8 — Run RagLibris for the First Time

Start the application or run the Google Drive authentication code.

If `token.json` does not exist, RagLibris executes:

```python
flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json",
    SCOPES
)

creds = flow.run_local_server(port=0)
```

A browser window will open.

Sign in using the Google account whose Drive should be accessed by RagLibris.

Review the requested permissions and click **Allow**.

### Step 9 — token.json Is Created Automatically

After successful authorization, RagLibris saves the credentials:

```python
with open("token.json", "w") as token:
    token.write(creds.to_json())
```

This creates:

```text
token.json
```

The file contains the authorization credentials required for subsequent API requests.

You do **not** need to manually create `token.json`.

### Step 10 — Subsequent Runs

On subsequent executions, RagLibris checks for `token.json`:

```python
if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file(
        "token.json",
        SCOPES
    )
```

If the credentials are still valid, RagLibris reuses them.

If the access token has expired but a refresh token is available:

```python
if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())
```

RagLibris refreshes the credentials automatically.

If valid credentials cannot be loaded, the OAuth login flow is started again.

### Credentials Summary

| File | Purpose | Commit to GitHub? |
|---|---|---|
| `credentials.json` | OAuth application/client configuration | ❌ No |
| `token.json` | User authorization credentials | ❌ No |
| `.env` | Application secrets/configuration | ❌ No |
| `.env.example` | Example configuration template | ✅ Yes |

### .gitignore

Add the following entries:

```gitignore
# Google OAuth credentials
credentials.json
token.json
```

Never commit OAuth credentials or access/refresh tokens to a public repository.

---

## ▶️ Running the Application**


### 1. Clone the repository


```bash

git clone <repository-url>

cd RagLibris

```


### 2. Create a virtual environment


```bash

python -m venv .venv

```


### 3. Activate the environment


Windows PowerShell:


```powershell

.venv\Scripts\Activate.ps1

```


### 4. Install dependencies


```bash

pip install -r requirements.txt

```


### 5. Configure environment variables


Create a `.env` file based on:


```text

.env.example

```


Add the required configuration values.


### 6. Start the backend


```bash

python -m uvicorn backend:app --host 0.0.0.0 --port 8000

```


### 7. Start the frontend


In another terminal:


```bash

streamlit run frontend.py

```


The application will be available at:


```text

http://localhost:8501

```


---


## 🖥️ Windows One-Click Launcher


The project also includes:


```text

start_RagLibris.bat

```


This launcher starts:


```text

FastAPI Backend

      ↓

Wait for API readiness

      ↓

Streamlit Frontend

      ↓

Open application

```


This allows RagLibris to be launched from a single desktop shortcut.


---


## 🎯 Skills Demonstrated


This project demonstrates practical implementation of:


### Python


- Modular Python development

- Exception handling

- Environment configuration

- File processing

- API integration


### AI / ML


- Text preprocessing

- Document chunking

- Embeddings

- Semantic search

- Vector databases

- Retrieval-Augmented Generation

- LLM integration


### RAG


- Document ingestion

- Chunking strategies

- Embedding generation

- Vector retrieval

- Context construction

- LLM response generation


### Software Engineering


- Modular architecture

- REST API development

- Frontend/backend separation

- Configuration management

- Incremental processing

- Error handling

- Git version control


### Cloud / Data Integration


- Google Drive integration

- Document synchronization

- Metadata management


---


## 🔮 Future Enhancements


Potential future improvements include:


- Streaming LLM responses

- Conversation-aware retrieval

- Hybrid keyword + vector search

- Reranking

- Multiple embedding models

- Document-level access control

- Citation/source display

- Evaluation framework for RAG quality

- Automated testing

- Docker deployment

- Kubernetes deployment

- Observability using Prometheus and Grafana


---


## 📌 Learning Objective


RagLibris was developed as a hands-on AI/ML project to move from theoretical understanding of machine learning and generative AI concepts toward practical implementation of a complete AI application.


The project focuses particularly on understanding how individual AI components—document processing, embeddings, vector databases, retrieval, APIs, and LLMs—can be combined into an end-to-end production-oriented RAG system.


---


## 👤 Author


**Santosh Mahadkar**


Infrastructure Architect | AI/ML Learner


This project is part of my ongoing AI/ML learning and hands-on experimentation.
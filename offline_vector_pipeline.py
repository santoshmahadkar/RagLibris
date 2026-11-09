"""Synchronize Google Drive documents into a persistent ChromaDB index.

The ingestion flow inventories Drive metadata, compares it with stored file
state, downloads new or modified supported files, extracts and classifies
their text, chunks it, and stores Ollama embeddings with source metadata.
"""

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import io
import json
import chromadb 
import ollama
from read_docx import read_docx_from_drive
from dotenv import load_dotenv
from read_docx import read_docx_from_drive
from resume_chunker import is_resume_text, chunk_resume_text
from generic_chunker import chunk_generic_text


load_dotenv()

# Runtime configuration is supplied through environment variables loaded above.
DB_PATH = os.getenv("DB_PATH")
SCOPES= [os.getenv("SCOPES")]
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
COLLECTION = os.getenv("COLLECTION")


# ------------------------------------------------------------
# Google Drive inventory and local metadata snapshot
# ------------------------------------------------------------

def scan_folder(creds, folder_id, file_path="", first_run=True):
    """Recursively list Drive files and append their metadata to a JSONL file.

    The first call truncates ``google_drive_metadata.jsonl``; recursive calls
    preserve that snapshot and append file records. Folder records are not
    written, but their names are carried into each file's ``folder_path``.
    Only the returned list of children is consumed; continuation tokens are not
    followed.

    Args:
        creds: Authorized Google OAuth credentials for Drive API access.
        folder_id: Drive folder whose children should be listed.
        file_path: Relative folder path accumulated during recursion.
        first_run: Whether to initialize the metadata snapshot before listing.

    Side effects:
        Calls the Google Drive API and writes file metadata locally.
    """

    # Empty JSONL file only on the first call
    if first_run:
        with open(
            "google_drive_metadata.jsonl",
            "w",
            encoding="utf-8"
        ) as output_file:
            pass

    # Connect to Google Drive
    service = build('drive', 'v3', credentials=creds)

    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    items = results.get('files', [])

    for item in items:

        item_id = item['id']
        item_name = item['name']
        mime_type = item['mimeType']

        item_path = os.path.join(file_path, item_name)

        if mime_type == 'application/vnd.google-apps.folder':

            scan_folder(
                creds,
                item_id,
                item_path,
                first_run=False
            )

        else:

            metadata = {
                "file_id": item_id,
                "file_name": item_name,
                "mime_type": mime_type,
                "parent_folder_id": folder_id,
                "folder_path": file_path,
                "source": "google_drive",
                "modified_time": item.get("modifiedTime"),
                "size": item.get("size"),
                "web_view_link": item.get("webViewLink")
            }

            with open("google_drive_metadata.jsonl", "a", encoding="utf-8") as output_file:
                output_file.write(json.dumps(metadata, ensure_ascii=False) + "\n")

            # print(json.dumps(metadata, ensure_ascii=False))


# ------------------------------------------------------------
# Chunking and index-state lookup helpers
# ------------------------------------------------------------

def chunk_text(text, chunk_size=1000, overlap=100):
    """Split text into fixed-width character slices with overlap.

    This legacy helper is not used by the current ingestion path, which selects
    the specialized resume or generic word-based chunker instead.
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

def get_existing_file_state(collection, file_id):
    """Read the first stored chunk's source version fields for a Drive file.

    Returns ``None`` when the collection has no matching metadata; otherwise
    the returned fields are compared with Drive's modified time and size.
    """

    print(f"Checking existance of file_id record : {file_id}")
    results = collection.get(
        where={"file_id": file_id},
        include=["metadatas"]
    )

    if not results["metadatas"]:
        return None
  
    metadata = results["metadatas"][0]
    return {
            "file_id": metadata.get("file_id"), 
            "modified_time": metadata.get("modified_time"), 
            "size": metadata.get("size")
    }

def get_unique_file_id_from_db(collection):
    """Return distinct non-null ``file_id`` values present in ChromaDB."""

    print("Getting unique file_ids from database")

    results = collection.get(
        include=["metadatas"]
    )

    file_ids = []

    for metadata in results["metadatas"]:
        file_id = metadata.get("file_id")

        if file_id is not None:
            file_ids.append(file_id)

    file_ids = list(set(file_ids))

    return file_ids

def get_unique_file_id_from_drive(file_name):
    """Load a Drive JSONL snapshot and return its distinct file IDs.

    File and JSON decoding errors are allowed to propagate to the caller.
    """

    print(f"Getting unique file_ids from google_drive")
    with open(file_name, "r", encoding="utf-8") as input_file:
        file_ids = []
        for line in input_file:
            metadata = json.loads(line)
            file_id = metadata["file_id"]
            file_ids.append(file_id)
        
        file_ids = list(set(file_ids))

        return file_ids


def get_chromadb_collection():
    """Open the configured persistent index or create a new collection.

    Existing database paths use the collection name from ``COLLECTION``;
    creation uses the fixed name ``google_drive_files`` and cosine distance.
    An existing path is assumed to contain the configured collection. Returns
    the client as well as the collection so both remain available.
    """

    print("Checking if database is already exists")
    if os.path.exists(DB_PATH):
        print("ChromaDB already exists.")

        client = chromadb.PersistentClient(
            path=DB_PATH
        )

        collection = client.get_collection(
            name=COLLECTION
        )

        print("Existing collection:", collection.name)

        return client, collection

    else:
        print("ChromaDB does not exist. Creating it...")

        client = chromadb.PersistentClient(
            path=DB_PATH
        )

        collection = client.create_collection(
            name="google_drive_files",
            metadata={"hnsw:space": "cosine"}
        )

        print("New collection:", collection.name)

        return client, collection


def main():
    """Synchronize Drive changes and index eligible document chunks.

    Reuses or refreshes ``token.json`` when possible, otherwise runs the
    installed-app OAuth flow using ``credentials.json``. Drive metadata is
    compared with ChromaDB to delete removed files and stage new or modified
    files. New and modified items are staged for processing, while deleted
    items have all their chunks removed. The staging JSONL is append-only, so
    prior entries may be processed again. Supported text is classified as a
    resume or a general document, embedded with Ollama's ``all-minilm:latest``,
    then stored with chunk and Drive metadata.

    The function writes local JSONL metadata and mutates the persistent
    ChromaDB collection. API, file, parsing, and embedding errors are not
    caught here; unsupported MIME types are logged and skipped.
    """

    creds = None

    # Reuse cached OAuth credentials, refreshing them when possible.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file(
            'token.json', SCOPES
        )

    # Start interactive OAuth only when there is no usable cached credential.
    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Build the Drive client used for file downloads and refresh the full metadata snapshot.
    service = build('drive', 'v3', credentials=creds)

    scan_folder(creds, GOOGLE_DRIVE_FOLDER_ID, "testing")

    client, collection = get_chromadb_collection()

    # Compare unique Drive IDs with indexed IDs to identify deletions and additions.
    db_file_ids = set(get_unique_file_id_from_db(collection))

    # Lets get all unique file_id from google_drive
    drive_file_ids = set(get_unique_file_id_from_drive("google_drive_metadata.jsonl"))

    deleted_files_on_drive = db_file_ids - drive_file_ids
    print(f"Total number of files recently deleted from Google Drive: {len(deleted_files_on_drive)}\n")

    new_file_added_to_drive = drive_file_ids - db_file_ids
    # print(type(new_file_added_to_drive))
    print(f"Total number of new files recently added to Google Drive: {len(new_file_added_to_drive)}\n")

    # Delete every chunk for files no longer present in the Drive snapshot.
    if len(deleted_files_on_drive) > 0:
        print(f"Checking if any files are recently deleted from google drive\n")
        for file_id in deleted_files_on_drive:
            print(f"This file_id: {file_id} is recently deleted from Google Drive hence we are deleting its record from from database collection: {collection}\n")
            result = collection.delete(
                where={
                    "file_id": file_id
                }
            )
    
    # Stage new files for processing; this JSONL file is opened in append mode.
    if len(new_file_added_to_drive) > 0:
        print(f"Checking if any new file recently added to Google Drive")
        with open("google_drive_metadata.jsonl", "r", encoding="utf-8") as input_file, \
            open("google_drive_metadata_new.jsonl", "a", encoding="utf-8") as output_file:
            for line in input_file:
                metadata = json.loads(line)

                file_id = metadata["file_id"]

                if file_id in new_file_added_to_drive:
                    print(f"Found file_id:{file_id} which is recently added to Google Drive, let's add it in a scope for embedding\n")
                    output_file.write(
                        json.dumps(metadata, ensure_ascii=False) + "\n"
                    )
                    print(f"Scope is added to google_drive_metadata_new.jsonl")

    print(f"After deleted files which were not available in Google Drive, lets take unique list of file_ids\n")
    db_file_ids = set(get_unique_file_id_from_db(collection))
    print(f"After deleting files from database, the number of file_id left in DB are: {len(db_file_ids)}\n")

    # Modified files are removed before their replacement chunks are indexed.
    if len(db_file_ids) > 0:
        print(f"Lets check if any file is recently modified, if it is then lets add in new scope for embedding\n")
        # Lets create a new jsonl file with only list of files which are not existed in chromadb
        with open("google_drive_metadata.jsonl", "r", encoding="utf-8") as input_file, \
            open("google_drive_metadata_new.jsonl", "a", encoding="utf-8") as output_file:
            for line in input_file:
                metadata = json.loads(line)
                existing_state = {}
                if metadata["file_id"] in db_file_ids:
                    file_id = metadata["file_id"]
                    modified_time = metadata["modified_time"]
                    size = metadata["size"]

                    existing_state = get_existing_file_state(collection, file_id)
                    
                    if existing_state is not None:
                        modified_time_db = existing_state["modified_time"]
                        size_db = existing_state["size"]

                        if modified_time != modified_time_db or size != size_db:
                            print(f"Found file_id: {file_id} is recently been modified and its embedding needs to be udpated\n")
                            print(f"First need to delete its record from database\n")
                            result = collection.delete(
                                where={
                                    "file_id": file_id
                                }
                            )
                            print(f"Records with {file_id} is deleted from database collection: {collection} - {result}\n")
                            print(f"Let's add file_id: {file_id} in new scope file: google_drive_metadata_new.jsonl\n")
                            output_file.write(
                                json.dumps(metadata, ensure_ascii=False) + "\n"
                            )
                    else:
                        print(f"file_id: {file_id} is not modified!")

    # Download and process the staged scope, including entries from prior runs
    # because the staging file is append-only in this implementation.
    with open("google_drive_metadata_new.jsonl", "r", encoding="utf-8") as input_file:
        print(f"Let's work on new scope\n")
        for line in input_file:
            metadata = json.loads(line)
            file_id = metadata["file_id"]
            mime_type = metadata["mime_type"]


            # Download the file content based on its mime type
            if mime_type == "application/vnd.google-apps.document":
                # Google Docs
                request = service.files().export_media(fileId=file_id, mimeType="text/plain")
                print(f"Downloading Google Docs file: {metadata['file_name']} (ID: {file_id})")
                file_content = request.execute()
                text = file_content.decode("utf-8")

            elif mime_type == "application/pdf":
                # The response bytes are decoded directly; no PDF text parser is used here.
                request = service.files().get_media(fileId=file_id)
                print(f"Downloading PDF file: {metadata['file_name']} (ID: {file_id})")
                file_content = request.execute()
                text = file_content.decode("utf-8", errors="ignore")

            elif mime_type.startswith("text/"):
                # Text files
                request = service.files().get_media(fileId=file_id)
                print(f"Downloading text file: {metadata['file_name']} (ID: {file_id})")
                file_content = request.execute()
                text = file_content.decode("utf-8", errors="ignore")

            elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                # The helper receives the Drive service and ID; file_content is not passed to it.
                request = service.files().get_media(fileId=file_id)
                print(f"Downloading DOCX file: {metadata['file_name']} (ID: {file_id})")
                file_content = request.execute()
                text = read_docx_from_drive(service, file_id)
            
            else:
                # Unsupported file types are not extracted or added to the index.
                print(f"Unsupported mime type: {mime_type} for file ID: {file_id}")
                continue

            # Resume detection uses extracted content, not the Drive filename.
            # Chunk the text and create the embeddings for each chunk.
            # ============================================================
            # DOCUMENT CHUNKING
            # ============================================================

            if is_resume_text(text):

                print(f"Detected resume: {metadata['file_name']}")

                chunks = chunk_resume_text(text, chunk_size=400, overlap=50)

            else:

                print(f"Detected normal document: {metadata['file_name']}")

                chunks = chunk_generic_text(text, chunk_size=1000, overlap=100)

            #Use all-minilm:latest emdbedding model running on local at 127.0.0.1:11434 for embedding generation. We will use the same metadata for each chunk of text.

            for i, chunk in enumerate(chunks):

                # Extract the actual text from the structured chunk
                chunk_text = chunk["text"]

                # Create embedding for the chunk using the local embedding model
                embedding = ollama.embed(
                    model="all-minilm:latest",
                    input=chunk_text
                )

                print(
                    f"Storing chunk {i + 1}/{len(chunks)} "
                    f"for file ID: {file_id} "
                    f"with file name: {metadata['file_name']}"
                )

                # Create chunk-specific metadata
                chunk_metadata = metadata.copy()

                chunk_metadata.update({
                    "section": chunk["section"],
                    "chunk_number": chunk["chunk_id"],
                    "word_count": chunk["word_count"]
                })

                # Store the chunk and its embedding in ChromaDB
                collection.add(
                    ids=[f"{file_id}_chunk_{i}"],
                    documents=[chunk_text],
                    metadatas=[chunk_metadata],
                    embeddings=[embedding.embeddings[0]]
                )
                
if __name__ == "__main__":
    main()
# DocuMind

DocuMind is a local React/Vite and FastAPI demo. It extracts text from one
small PDF, creates page-labelled chunks, embeds them with Sentence Transformers,
searches those chunks with FAISS, then sends the retrieved text to Google Gemini.
The application does not keep a persistent PDF copy; multipart uploads may be
temporarily spooled by FastAPI and the upload stream is closed after its
size-limited read. The document index is in memory and is cleared when the
backend stops.

## Requirements

- Python 3.11 (the supplied virtual environment uses Python 3.11)
- Node.js and npm
- A Google Gemini API key

The current embedding model is `sentence-transformers/all-MiniLM-L6-v2`. It is
a local embedding model, not a local chat model. Its code documentation lists
about 80 MB of model weights; on this machine the existing Hugging Face cache
is approximately 183 MB. PyTorch uses additional RAM while loading/inferencing.
The app loads the embedder on the first PDF upload, not at server startup. The
model is already cached on this machine, so using it here does not need another
model download. A fresh machine may download it on first upload.

## Configure the API key

The backend reads `backend/.env`. Keep `GEMINI_API_KEY` there only; do not add
it to React or any `VITE_` variable. The existing local `.env` is ignored by
Git. If setting up a fresh copy:

```powershell
cd "D:\AI POWERED PDF CHATBOT\documind-ai\backend"
Copy-Item .env.example .env
notepad .env
```

Set:

```dotenv
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```

Optional backend settings include `MAX_UPLOAD_SIZE` (bytes, default
`10485760`), `TOP_K_CHUNKS` (default `5`), `RELEVANCE_THRESHOLD` (default
`0.2`), `CHUNK_SIZE` (default `800`), and `CHUNK_OVERLAP` (default `150`).

## Run on Windows PowerShell

Open two PowerShell terminals.

Backend:

```powershell
cd "D:\AI POWERED PDF CHATBOT\documind-ai\backend"
if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) { python -m venv venv }
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The install command is needed on a fresh checkout; it uses the dependencies
listed for the backend. The embedding model can download on first PDF upload
if it is not already cached.

Frontend:

```powershell
cd "D:\AI POWERED PDF CHATBOT\documind-ai\frontend"
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally http://localhost:5173).
FastAPI docs are at http://127.0.0.1:8000/docs. Stop each server with
`Ctrl+C`; restart by running the same commands again.

## Demonstrate it

1. Keep both servers running and open the frontend.
2. Upload a text-based PDF smaller than 10 MB. Only one document can be loaded
   at a time; remove it before uploading another.
3. Ask a question whose answer appears explicitly in the PDF.
4. Expand the source cards to verify the cited page and retrieved passage.
5. Ask about something absent from the PDF; the app should say it could not
   find that information rather than answer from general knowledge.
6. Try a scanned/image-only PDF to see the OCR-not-supported explanation.

## Limits and privacy notes

Gemini has provider/account/model quotas. This app cannot guarantee unlimited
usage; it reports quota exhaustion separately and retries only a small,
bounded number of transient rate-limit or service/network failures. It makes no
automatic paid-provider switch and does not make an LLM request during startup.
Retrieved PDF passages are sent to Gemini for question answering, so do not use
confidential documents unless that sharing is acceptable to you.

This is a local demonstration, not a production-secure multi-user service. The
backend keeps a single active document/index in process memory, uses a
localhost-only development server, and has no authentication or user accounts.

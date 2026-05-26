"""FastAPI backend — wraps the RAG pipeline as REST + SSE endpoints."""
import json
import os
import shutil
import sys
from pathlib import Path

import certifi
import truststore

truststore.inject_into_ssl()
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import cohere
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

from rag_chatbot import (
    DATA_DIR, LLM_MODEL, SUPPORTED_EXTS, SYSTEM_PROMPT,
    build_prompt, get_pinecone_index, ingest_file, ingest_path,
    ingested_sources, pinecone_delete_all, pinecone_total_vectors,
    retrieve_context, save_ingest_log,
)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
cohere_client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))
index = get_pinecone_index()

app = FastAPI(title="EduBot API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


@app.get("/api/status")
def get_status():
    return {
        "total_vectors": pinecone_total_vectors(index),
        "sources_count": len(ingested_sources()),
    }


@app.get("/api/sources")
def get_sources():
    return ingested_sources()


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Stream answer tokens via Server-Sent Events."""
    async def generate():
        try:
            chunks = retrieve_context(req.question, index, openai_client, cohere_client)
            safe = [
                {k: (float(v) if isinstance(v, float) else v) for k, v in c.items()}
                for c in chunks
            ]
            yield f"data: {json.dumps({'type': 'chunks', 'data': safe})}\n\n"

            stream = openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": build_prompt(req.question, chunks)},
                ],
                temperature=0.3,
                max_tokens=512,
                stream=True,
            )
            for part in stream:
                token = part.choices[0].delta.content or ""
                if token:
                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'data': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/ingest")
async def ingest_upload(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTS:
        raise HTTPException(400, f"Unsupported type '{suffix}'. Use .txt or .pdf")
    DATA_DIR.mkdir(exist_ok=True)
    target = DATA_DIR / file.filename
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    added = ingest_file(target, index, openai_client)
    return {"filename": file.filename, "added": added, "total": pinecone_total_vectors(index)}


@app.post("/api/rebuild")
def rebuild():
    pinecone_delete_all(index)
    save_ingest_log({})
    added = ingest_path(DATA_DIR, index, openai_client)
    return {"added": added, "total": pinecone_total_vectors(index)}


# Serve built frontend
_dist = Path(__file__).parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")

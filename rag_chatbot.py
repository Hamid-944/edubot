"""
RAG-Based Educational Chatbot for School Students
==================================================

Pipeline:
  ingest_file()
      -> chunk_text()                      # sentence-aware sliding window
      -> get_embeddings()                  # OpenAI text-embedding-3-small
      -> pinecone_index.upsert()           # Pinecone vector DB

  ask()
      -> get_embeddings(question)          # embed the query
      -> pinecone_index.query(top_k=10)   # broad candidate retrieval
      -> cohere_rerank(top_n=3)            # precision reranking
      -> build_prompt()                    # context-first prompt template
      -> gpt-4o-mini                       # answer generation
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import certifi
import truststore

# Inject the Windows certificate store into Python's SSL context.
# This handles corporate networks that do SSL inspection with a private CA —
# the corporate root cert lives in the Windows store, not in certifi's bundle.
truststore.inject_into_ssl()

# Fallback env-vars for requests-based clients (Cohere SDK)
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
os.environ.setdefault("SSL_CERT_FILE",      certifi.where())

import cohere
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from rich import box
from rich.align import Align
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL    = "text-embedding-3-small"
EMBEDDING_DIM      = 1536
LLM_MODEL          = "gpt-4o-mini"
RERANK_MODEL       = "rerank-english-v3.0"
CHUNK_SIZE         = 500
CHUNK_OVERLAP      = 100
PINECONE_RETRIEVE_K = 10   # broad retrieval from Pinecone
TOP_K              = 3     # final chunks after Cohere reranking
DATA_DIR           = Path("data")
INGEST_LOG_PATH    = Path("ingest_log.json")
SUPPORTED_EXTS     = {".txt", ".pdf"}

console = Console()

SUBJECT_COLORS = {
    "mathematics":   "yellow",
    "science":       "green",
    "english":       "blue",
    "social studies":"magenta",
}

def subject_color(subject: str) -> str:
    return SUBJECT_COLORS.get(subject.lower(), "cyan")


# ── Task 2: Chunking ──────────────────────────────────────────────────────────

def chunk_text(text: str,
               chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        slen = len(sentence) + 1
        if current_len + slen > chunk_size and current:
            chunks.append(" ".join(current))
            tail: List[str] = []
            tail_len = 0
            for s in reversed(current):
                if tail_len + len(s) + 1 <= overlap:
                    tail.insert(0, s)
                    tail_len += len(s) + 1
                else:
                    break
            current = tail
            current_len = tail_len
        current.append(sentence)
        current_len += slen

    if current:
        chunks.append(" ".join(current))
    return chunks


def chunks_with_positions(text: str) -> List[dict]:
    """
    Returns chunks enriched with approximate character positions so the
    debug view can show exactly where in the document each chunk lives.
    """
    raw = chunk_text(text)
    result = []
    search_from = 0
    for chunk in raw:
        key = chunk[:60]
        pos = text.find(key, max(0, search_from - CHUNK_OVERLAP * 2))
        if pos == -1:
            pos = search_from
        result.append({
            "text":       chunk,
            "char_start": pos,
            "char_end":   pos + len(chunk),
        })
        search_from = pos + len(chunk) - CHUNK_OVERLAP
    return result


# ── Document readers ──────────────────────────────────────────────────────────

def read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        console.print(Panel("[red]pypdf not installed.[/]\nRun: pip install pypdf",
                            border_style="red"))
        return ""
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_file(path: Path) -> str:
    return read_pdf(path) if path.suffix.lower() == ".pdf" else read_txt(path)


# ── Ingest log (local JSON — tracks what has been ingested) ──────────────────

def load_ingest_log() -> dict:
    if INGEST_LOG_PATH.exists():
        return json.loads(INGEST_LOG_PATH.read_text(encoding="utf-8"))
    return {}


def save_ingest_log(log: dict):
    INGEST_LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")


def already_ingested(filename: str) -> bool:
    return filename in load_ingest_log()


def ingested_sources() -> dict:
    return load_ingest_log()


# ── Pinecone ──────────────────────────────────────────────────────────────────

def get_pinecone_index():
    api_key    = os.getenv("PINECONE_API_KEY", "")
    index_name = os.getenv("PINECONE_INDEX_NAME", "edubot")

    if not api_key or api_key.startswith("your-"):
        console.print(Panel(
            "[red bold]PINECONE_API_KEY not set.[/]\n"
            "[dim]Add it to your [cyan].env[/] file.[/]",
            border_style="red", box=box.ROUNDED,
        ))
        sys.exit(1)

    pc = Pinecone(api_key=api_key, ssl_ca_certs=certifi.where())
    existing_names = [idx.name for idx in pc.list_indexes()]

    if index_name not in existing_names:
        console.print(Panel(
            f"[yellow]Creating Pinecone index [bold]{index_name!r}[/] "
            f"(dim={EMBEDDING_DIM}, metric=cosine)...[/]",
            border_style="yellow", box=box.ROUNDED,
        ))
        pc.create_index(
            name=index_name,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        with console.status("[yellow]Waiting for index to become ready...[/]"):
            while not pc.describe_index(index_name).status.ready:
                time.sleep(1)
        console.print(f"[green]Index {index_name!r} is ready.[/]\n")

    return pc.Index(index_name)


def pinecone_total_vectors(index) -> int:
    try:
        return index.describe_index_stats().total_vector_count
    except Exception:
        return 0


def pinecone_delete_all(index):
    try:
        index.delete(delete_all=True)
    except Exception:
        pass


# ── Task 3: Embeddings ────────────────────────────────────────────────────────

def get_embeddings(texts: List[str], client: OpenAI) -> List[List[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


# ── Ingest pipeline ───────────────────────────────────────────────────────────

def ingest_file(path: Path,
                index,
                openai_client: OpenAI,
                force: bool = False) -> int:
    filename = path.name

    if not force and already_ingested(filename):
        console.print(
            f"  [dim]Skipped[/dim] [cyan]{filename}[/cyan]"
            "[dim] — already in knowledge base[/dim]"
        )
        return 0

    text = read_file(path)
    if not text.strip():
        console.print(Panel(f"[yellow]No text extracted from {filename}[/]",
                            border_style="yellow"))
        return 0

    chunk_data   = chunks_with_positions(text)
    subject      = path.stem.replace("_", " ").title()
    color        = subject_color(subject)
    total_chunks = len(chunk_data)
    file_size    = path.stat().st_size
    ingested_at  = datetime.now().isoformat()

    all_embeddings: List[List[float]] = []

    with Progress(
        SpinnerColumn(style=f"bold {color}"),
        TextColumn(f"  [bold {color}]{{task.description}}[/]"),
        BarColumn(bar_width=36, style=color, complete_style=f"bold {color}"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as bar:
        task = bar.add_task(filename, total=total_chunks)
        for i in range(0, total_chunks, 100):
            batch_data = chunk_data[i : i + 100]
            batch_texts = [c["text"] for c in batch_data]
            all_embeddings.extend(get_embeddings(batch_texts, openai_client))
            bar.advance(task, len(batch_data))

    # Build Pinecone vectors with rich metadata
    vectors = [
        {
            "id": f"{filename}_chunk_{i}",
            "values": embedding,
            "metadata": {
                "text":         c["text"],
                "source":       filename,
                "subject":      subject,
                "file_type":    path.suffix.lstrip(".").upper(),
                "file_size_kb": round(file_size / 1024, 1),
                "chunk_index":  i,
                "total_chunks": total_chunks,
                "char_start":   c["char_start"],
                "char_end":     c["char_end"],
                "chunk_size":   len(c["text"]),
                "ingested_at":  ingested_at,
            },
        }
        for i, (c, embedding) in enumerate(zip(chunk_data, all_embeddings))
    ]

    # Upsert in batches of 100
    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i : i + 100])

    # Update local ingest log
    log = load_ingest_log()
    log[filename] = {
        "subject":      subject,
        "file_type":    path.suffix.lstrip(".").upper(),
        "file_size_kb": round(file_size / 1024, 1),
        "total_chunks": total_chunks,
        "ingested_at":  ingested_at,
    }
    save_ingest_log(log)

    console.print(
        f"  [bold {color}]+[/] [bold]{total_chunks} chunks[/] "
        f"stored from [cyan]{filename}[/]\n"
    )
    return total_chunks


def ingest_path(target: Path, index, openai_client: OpenAI,
                force: bool = False) -> int:
    if target.is_file():
        if target.suffix.lower() not in SUPPORTED_EXTS:
            console.print(Panel(
                f"[red]Unsupported type:[/] {target.suffix}\n"
                f"[dim]Supported: {', '.join(sorted(SUPPORTED_EXTS))}[/]",
                border_style="red",
            ))
            return 0
        return ingest_file(target, index, openai_client, force=force)

    if target.is_dir():
        files = [f for f in sorted(target.iterdir())
                 if f.suffix.lower() in SUPPORTED_EXTS]
        if not files:
            console.print(Panel(
                f"[yellow]No .txt or .pdf files found in {target}/[/]",
                border_style="yellow",
            ))
            return 0
        total = 0
        for f in files:
            total += ingest_file(f, index, openai_client, force=force)
        return total

    console.print(Panel(f"[red]Path not found:[/] {target}", border_style="red"))
    return 0


# ── Retrieval + Cohere reranking ──────────────────────────────────────────────

def retrieve_candidates(question: str,
                        index,
                        openai_client: OpenAI,
                        k: int = PINECONE_RETRIEVE_K) -> List[dict]:
    """Query Pinecone for the top-k semantically similar chunks."""
    q_embedding = get_embeddings([question], openai_client)[0]
    results = index.query(
        vector=q_embedding,
        top_k=k,
        include_metadata=True,
    )
    return [
        {
            "text":         m.metadata.get("text", ""),
            "source":       m.metadata.get("source", "unknown"),
            "subject":      m.metadata.get("subject", "Unknown"),
            "file_type":    m.metadata.get("file_type", "TXT"),
            "file_size_kb": m.metadata.get("file_size_kb", 0),
            "chunk_index":  int(m.metadata.get("chunk_index", 0)),
            "total_chunks": int(m.metadata.get("total_chunks", 0)),
            "char_start":   int(m.metadata.get("char_start", 0)),
            "char_end":     int(m.metadata.get("char_end", 0)),
            "chunk_size":   int(m.metadata.get("chunk_size", 0)),
            "ingested_at":  m.metadata.get("ingested_at", ""),
            "pinecone_score": round(m.score, 4),
            "rerank_score":   None,
            "rerank_rank":    None,
        }
        for m in results.matches
    ]


def rerank_with_cohere(question: str,
                       candidates: List[dict],
                       cohere_client,
                       top_n: int = TOP_K) -> List[dict]:
    """Rerank candidate chunks with Cohere and keep top_n."""
    if not candidates:
        return []

    response = cohere_client.rerank(
        model=RERANK_MODEL,
        query=question,
        documents=[c["text"] for c in candidates],
        top_n=min(top_n, len(candidates)),
    )

    reranked = []
    for rank, r in enumerate(response.results, start=1):
        chunk = candidates[r.index].copy()
        chunk["rerank_score"] = round(r.relevance_score, 4)
        chunk["rerank_rank"]  = rank
        reranked.append(chunk)
    return reranked


def retrieve_context(question: str,
                     index,
                     openai_client: OpenAI,
                     cohere_client) -> List[dict]:
    """Full retrieval: Pinecone (broad) -> Cohere rerank (precise)."""
    candidates = retrieve_candidates(question, index, openai_client)
    return rerank_with_cohere(question, candidates, cohere_client)


# ── Task 4: Prompt Engineering ────────────────────────────────────────────────

SYSTEM_PROMPT = """You are EduBot, a warm and encouraging AI tutor for school students aged 10-14.

Guidelines:
- Answer ONLY using the context provided - do NOT invent or assume facts.
- If the context does not contain enough information, say:
  "I don't have enough information about that in my study materials right now."
- Use simple, clear language appropriate for middle-school students.
- Break down complex ideas with step-by-step reasoning or relatable examples.
- Keep answers focused: 3-6 sentences unless a worked example is necessary.
- You may use **bold** or bullet points to make answers clearer."""


def build_prompt(question: str, chunks: List[dict]) -> str:
    context_parts = [
        f"[Source {i} - {c['subject']}]\n{c['text']}"
        for i, c in enumerate(chunks, 1)
    ]
    return (
        "Use ONLY the study material excerpts below to answer the question.\n"
        "If the answer cannot be found in the excerpts, say so.\n\n"
        f"STUDY MATERIAL:\n\n{chr(10).join(context_parts)}\n\n"
        f"STUDENT QUESTION: {question}\n\n"
        "ANSWER (clear and student-friendly):"
    )


# ── LLM call ──────────────────────────────────────────────────────────────────

def ask(question: str,
        index,
        openai_client: OpenAI,
        cohere_client) -> Tuple[str, List[dict]]:
    chunks = retrieve_context(question, index, openai_client, cohere_client)
    prompt = build_prompt(question, chunks)
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.3,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip(), chunks


# ── Rich UI helpers ───────────────────────────────────────────────────────────

def print_banner():
    title = Text(justify="center")
    title.append("E D U B O T\n", style="bold bright_blue")
    title.append("RAG + Pinecone + Cohere Reranker\n\n", style="bold white")
    title.append("Mathematics  |  Science  |  English  |  Social Studies",
                 style="dim cyan")
    console.print()
    console.print(Panel(
        Align.center(title),
        border_style="bright_blue",
        padding=(1, 8),
        box=box.DOUBLE_EDGE,
    ))
    console.print()


def print_help():
    table = Table(
        box=box.ROUNDED, border_style="bright_blue",
        show_header=True, header_style="bold bright_blue", padding=(0, 1),
    )
    table.add_column("Command", style="bold cyan", min_width=22)
    table.add_column("Description", style="white")
    rows = [
        ("ingest",           "Scan data/ and add any new .txt / .pdf files"),
        ("ingest <path>",    "Add a specific file or folder to the knowledge base"),
        ("ingest --rebuild", "Wipe Pinecone + log, re-ingest data/ from scratch"),
        ("list",             "Show every ingested file with metadata"),
        ("debug <question>", "Answer and display full retrieval + rerank metadata"),
        ("help",             "Show this command reference"),
        ("quit",             "Exit EduBot"),
    ]
    for cmd, desc in rows:
        table.add_row(cmd, desc)
    console.print(Panel(table, title="[bold bright_blue] Commands [/]",
                        border_style="bright_blue", padding=(0, 1)))


def print_sources():
    log = ingested_sources()
    if not log:
        console.print(Panel("[yellow]No documents have been ingested yet.[/]",
                            border_style="yellow"))
        return

    table = Table(
        box=box.ROUNDED, border_style="bright_blue",
        show_header=True, header_style="bold bright_blue", show_lines=True,
    )
    table.add_column("File",       style="cyan", min_width=24)
    table.add_column("Subject",    min_width=16)
    table.add_column("Type",       justify="center", min_width=6)
    table.add_column("Size (KB)",  justify="right", min_width=9)
    table.add_column("Chunks",     justify="right", style="bold green", min_width=7)
    table.add_column("Ingested At", style="dim", min_width=20)

    total = 0
    for src, info in sorted(log.items()):
        subject = info.get("subject", "Unknown")
        color   = subject_color(subject)
        table.add_row(
            src,
            f"[{color}]{subject}[/]",
            info.get("file_type", "TXT"),
            str(info.get("file_size_kb", "?")),
            str(info.get("total_chunks", "?")),
            info.get("ingested_at", "")[:19],
        )
        total += info.get("total_chunks", 0)

    table.add_section()
    table.add_row("[bold]TOTAL[/]", "", "", "", f"[bold green]{total}[/]", "")

    console.print(Panel(
        table,
        title="[bold bright_blue] Knowledge Base — Ingested Documents [/]",
        border_style="bright_blue", padding=(0, 1),
    ))


def _score_bar(score: float, width: int = 14, color: str = "green") -> str:
    filled = round(score * width)
    return f"[{color}]" + "#" * filled + "[/]" + "[dim]" + "-" * (width - filled) + "[/]"


def print_answer(answer: str, chunks: List[dict], debug: bool):
    border = subject_color(chunks[0]["subject"]) if chunks else "green"

    console.print(Panel(
        Markdown(answer),
        title=f"[bold {border}] EduBot [/]",
        border_style=border,
        padding=(1, 2),
        box=box.ROUNDED,
    ))

    if not debug:
        return

    console.print(Rule("[dim] Retrieved Context — Pinecone + Cohere Reranker [/]",
                       style="dim blue"))

    for c in chunks:
        color        = subject_color(c["subject"])
        pscore       = c["pinecone_score"]
        rscore       = c["rerank_score"]
        rank         = c["rerank_rank"]

        # Metadata table
        meta = Table(box=None, show_header=False, padding=(0, 1), expand=True)
        meta.add_column(style="dim", min_width=16)
        meta.add_column(style="white")

        meta.add_row("Source file",  f"[cyan]{c['source']}[/]")
        meta.add_row("Subject",      f"[{color}]{c['subject']}[/]")
        meta.add_row("File type",    c["file_type"])
        meta.add_row("File size",    f"{c['file_size_kb']} KB")
        meta.add_row("Chunk",
                     f"[bold]#{c['chunk_index'] + 1}[/] of "
                     f"[bold]{c['total_chunks']}[/]  "
                     f"[dim](chars {c['char_start']:,} - {c['char_end']:,}, "
                     f"{c['chunk_size']} chars)[/dim]")
        meta.add_row("Ingested at",  f"[dim]{c['ingested_at'][:19]}[/]")
        meta.add_section()
        meta.add_row("Pinecone sim",
                     f"{pscore:.4f}  {_score_bar(pscore, color='bright_blue')}")
        meta.add_row("Cohere rank",
                     f"[bold]#{rank}[/]  score {rscore:.4f}  "
                     f"{_score_bar(rscore if rscore else 0, color=color)}")

        console.print(Panel(
            meta,
            title=f"[bold {color}] Chunk #{c['chunk_index'] + 1} — {c['subject']} [/]"
                  f"[dim]  {c['source']}[/dim]",
            subtitle=f"[dim] Rerank #{rank}  |  "
                     f"Pinecone {pscore:.4f}  |  Cohere {rscore:.4f} [/dim]",
            border_style=color,
            box=box.ROUNDED,
            padding=(0, 1),
        ))

        console.print(Panel(
            Text(c["text"], style="dim"),
            title=f"[dim] Text [/dim]",
            border_style="dim",
            box=box.MINIMAL,
            padding=(0, 1),
        ))
        console.print()

    console.print(Rule(style="dim blue"))


def print_ingest_summary(added: int, total: int):
    if added > 0:
        console.print(Panel(
            f"[bold green]+{added} new chunks[/] added  "
            f"[dim]|[/]  total in Pinecone: [bold]{total}[/]",
            border_style="green", padding=(0, 1),
        ))
    else:
        console.print(Panel(
            "[yellow]No new chunks added — all files already ingested.[/]",
            border_style="yellow", padding=(0, 1),
        ))


# ── Startup menus ─────────────────────────────────────────────────────────────

def startup_menu(index, openai_client: OpenAI) -> bool:
    """Returns False if the user chose to exit."""
    log    = ingested_sources()
    total  = pinecone_total_vectors(index)

    rows = "\n".join(
        f"  [{subject_color(info.get('subject','Unknown'))}]"
        f"{src}[/]  [dim]{info.get('total_chunks',0)} chunks  "
        f"{info.get('ingested_at','')[:10]}[/]"
        for src, info in sorted(log.items())
    )
    console.print(Panel(
        f"[bold green]{total} vectors[/] across "
        f"[bold]{len(log)}[/] file(s)\n\n{rows}" if rows
        else f"[bold green]{total} vectors[/] in index",
        title="[bold green] Pinecone Knowledge Base Ready [/]",
        border_style="green", padding=(0, 2), box=box.ROUNDED,
    ))

    console.print(Panel(
        "  [bold cyan][1][/]  Start chatting\n"
        "  [bold cyan][2][/]  Ingest more documents from data/ folder\n"
        "  [bold cyan][3][/]  Rebuild knowledge base from scratch\n"
        "  [bold cyan][4][/]  Exit",
        title="[bold bright_blue] What would you like to do? [/]",
        border_style="bright_blue", padding=(0, 2), box=box.ROUNDED,
    ))

    while True:
        choice = console.input("\n[bold bright_blue]  Choice (1/2/3/4): [/]").strip()
        if choice == "1":
            return True
        if choice == "2":
            console.print(Rule("[dim] Ingesting documents [/]", style="dim green"))
            added = ingest_path(DATA_DIR, index, openai_client)
            print_ingest_summary(added, pinecone_total_vectors(index))
            return True
        if choice == "3":
            console.print(Rule("[dim] Rebuilding Knowledge Base [/]", style="dim yellow"))
            pinecone_delete_all(index)
            save_ingest_log({})
            added = ingest_path(DATA_DIR, index, openai_client)
            print_ingest_summary(added, pinecone_total_vectors(index))
            return True
        if choice == "4":
            return False
        console.print("[red]  Please enter 1, 2, 3, or 4.[/]")


def first_run_menu(index, openai_client: OpenAI) -> bool:
    """Returns False if the user chose to exit."""
    console.print(Panel(
        "  [bold cyan][1][/]  Ingest all documents from [cyan]data/[/] folder\n"
        "  [bold cyan][2][/]  Ingest a specific file or folder path\n"
        "  [bold cyan][3][/]  Exit",
        title="[bold yellow] No Knowledge Base Found — Pinecone index is empty [/]",
        border_style="yellow", padding=(0, 2), box=box.ROUNDED,
    ))

    while True:
        choice = console.input("\n[bold yellow]  Choice (1/2/3): [/]").strip()

        if choice == "1":
            console.print(Rule("[dim] Ingesting documents [/]", style="dim green"))
            added = ingest_path(DATA_DIR, index, openai_client)
            if added == 0:
                console.print(Panel(f"[red]No supported files found in {DATA_DIR}/[/]",
                                    border_style="red"))
                return False
            return True

        if choice == "2":
            raw_path = console.input("[bold]  Enter file or folder path: [/]").strip()
            console.print(Rule("[dim] Ingesting [/]", style="dim green"))
            added = ingest_path(Path(raw_path), index, openai_client)
            return added > 0

        if choice == "3":
            return False

        console.print("[red]  Please enter 1, 2, or 3.[/]")


# ── Task 5: Chatbot REPL ──────────────────────────────────────────────────────

def _check_env():
    errors = []
    if not os.getenv("OPENAI_API_KEY"):
        errors.append("OPENAI_API_KEY")
    pk = os.getenv("PINECONE_API_KEY", "")
    if not pk or pk.startswith("your-"):
        errors.append("PINECONE_API_KEY")
    ck = os.getenv("COHERE_API_KEY", "")
    if not ck or ck.startswith("your-"):
        errors.append("COHERE_API_KEY")
    if errors:
        console.print(Panel(
            "[red bold]Missing API keys in .env:[/]\n"
            + "\n".join(f"  [yellow]{k}[/]" for k in errors),
            border_style="red", box=box.ROUNDED,
        ))
        sys.exit(1)


def run():
    _check_env()

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    cohere_client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))

    print_banner()

    with console.status("[bold yellow]  Connecting to Pinecone...[/]", spinner="dots"):
        index = get_pinecone_index()

    total = pinecone_total_vectors(index)

    if total > 0:
        ready = startup_menu(index, openai_client)
    else:
        ready = first_run_menu(index, openai_client)

    if not ready:
        console.print(Panel("[dim]Goodbye! Come back when you're ready to learn.[/]",
                            border_style="dim"))
        sys.exit(0)

    if pinecone_total_vectors(index) == 0:
        console.print(Panel("[red]Knowledge base is empty. Ingest some documents first.[/]",
                            border_style="red"))
        sys.exit(1)

    console.print()
    console.print(Panel(
        f"[bold green]Pinecone:[/]   {pinecone_total_vectors(index)} vectors\n"
        f"[bold green]Retrieval:[/]  top-{PINECONE_RETRIEVE_K} from Pinecone "
        f"-> top-{TOP_K} via Cohere reranker\n"
        "[dim]Ask any question, or type [bold cyan]help[/bold cyan] for commands.[/dim]",
        border_style="green", box=box.ROUNDED, padding=(0, 2),
    ))
    console.print()

    # ── Chat loop ─────────────────────────────────────────────────────────────
    while True:
        try:
            raw = console.input("[bold bright_blue] You [/][dim]>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print(Panel("[dim]Goodbye! Keep studying![/]", border_style="dim"))
            break

        if not raw:
            continue

        low = raw.lower()

        if low in {"quit", "exit", "q"}:
            console.print(Panel("[dim]Goodbye! Keep studying![/]", border_style="dim"))
            break

        if low == "help":
            print_help()
            continue

        if low == "list":
            print_sources()
            continue

        if low == "ingest --rebuild":
            console.print(Rule("[dim] Rebuilding Knowledge Base [/]", style="dim yellow"))
            pinecone_delete_all(index)
            save_ingest_log({})
            added = ingest_path(DATA_DIR, index, openai_client)
            print_ingest_summary(added, pinecone_total_vectors(index))
            continue

        if low == "ingest" or low.startswith("ingest "):
            parts  = raw.split(maxsplit=1)
            target = Path(parts[1].strip()) if len(parts) > 1 else DATA_DIR
            console.print(Rule("[dim] Ingesting [/]", style="dim green"))
            added = ingest_path(target, index, openai_client)
            print_ingest_summary(added, pinecone_total_vectors(index))
            continue

        # ── Question answering ────────────────────────────────────────────────
        debug    = low.startswith("debug ")
        question = raw[6:].strip() if debug else raw
        if not question:
            continue

        with console.status(
            "[bold yellow]  Retrieving from Pinecone + reranking with Cohere...[/]",
            spinner="dots",
        ):
            answer, chunks = ask(question, index, openai_client, cohere_client)

        console.print()
        print_answer(answer, chunks, debug)
        console.print()


if __name__ == "__main__":
    run()

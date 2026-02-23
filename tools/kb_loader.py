"""
Knowledge base loader with keyword search for Designer agent.
Phase 1: paragraph chunking + keyword scoring.
Phase 2: swap in vector search (Qdrant/Pinecone).
"""
from pathlib import Path

KB_DIR = Path(__file__).parent.parent / "data" / "kb"
CHUNK_SIZE = 600  # chars per chunk


def _load_chunks(exclude: set[str] | None = None) -> list[tuple[str, str]]:
    """Return list of (source_filename, chunk_text) from all KB .md files."""
    exclude = exclude or set()
    chunks = []
    for md_file in sorted(KB_DIR.glob("*.md")):
        if md_file.name in exclude:
            continue
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            if len(para) > CHUNK_SIZE:
                for i in range(0, len(para), CHUNK_SIZE):
                    chunk = para[i : i + CHUNK_SIZE].strip()
                    if chunk:
                        chunks.append((md_file.name, chunk))
            else:
                chunks.append((md_file.name, para))
    return chunks


def search(query: str, top_k: int = 4, exclude: set[str] | None = None) -> str:
    """
    Keyword search over KB markdown files.
    Returns a formatted string of the top_k most relevant chunks.
    """
    chunks = _load_chunks(exclude=exclude)
    if not chunks:
        return (
            "No knowledge base files found. "
            "Please upload .md files in Settings → AI Designer."
        )

    query_words = set(query.lower().split())

    def score(text: str) -> int:
        t = text.lower()
        return sum(1 for w in query_words if w in t)

    scored = sorted(
        [(score(text), src, text) for src, text in chunks],
        reverse=True,
        key=lambda x: x[0],
    )
    top = scored[:top_k]

    # If no keyword match, fall back to first top_k chunks
    if not top or top[0][0] == 0:
        top = [(0, src, text) for src, text in chunks[:top_k]]

    parts = [f"[{src}]\n{text}" for _, src, text in top]
    return "\n\n---\n\n".join(parts)

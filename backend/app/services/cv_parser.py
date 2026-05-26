import hashlib
import re
from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi import HTTPException, UploadFile
from pypdf import PdfReader


SECTION_HINTS = {
    "summary": "Summary",
    "profile": "Summary",
    "experience": "Experience",
    "employment": "Experience",
    "projects": "Projects",
    "skills": "Skills",
    "education": "Education",
    "certifications": "Certifications",
}


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.replace("\x00", "")
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:160] or "cv.txt"


async def read_upload(upload: UploadFile, max_bytes: int) -> tuple[str, bytes]:
    filename = sanitize_filename(upload.filename or "cv.txt")
    content = await upload.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"CV upload exceeds {max_bytes // 1024 // 1024} MB limit")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded CV is empty")
    return filename, content


def extract_text_from_bytes(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(content)
    if suffix == ".docx":
        return _extract_docx(content)
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="replace")
    raise HTTPException(status_code=400, detail="Unsupported CV type. Upload PDF, DOCX, or TXT.")


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text(extraction_mode="layout") or "")
        except TypeError:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _extract_docx(content: bytes) -> str:
    doc = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())


def clean_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text)
    text = "\n".join(_repair_spaced_pdf_line(line) for line in text.splitlines())
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _repair_spaced_pdf_line(line: str) -> str:
    tokens = line.strip().split()
    if len(tokens) < 8:
        return line.strip()
    single_char_tokens = sum(1 for token in tokens if len(token) == 1)
    if single_char_tokens / len(tokens) < 0.65:
        return line.strip()
    joined = "".join(tokens)
    joined = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", joined)
    joined = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", joined)
    joined = re.sub(r"(?<=[A-Za-z])(?=\d{2,})", " ", joined)
    joined = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", joined)
    joined = joined.replace("|", " | ")
    return joined


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_cv(text: str, max_chars: int = 900) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines()]
    chunks: list[dict[str, str]] = []
    current_section = "General"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        joined = "\n".join(buffer).strip()
        if joined:
            chunks.extend(_split_long_chunk(current_section, joined, max_chars))
        buffer = []

    for line in lines:
        if not line:
            continue
        maybe_section = _section_from_line(line)
        if maybe_section and len(line) <= 60:
            flush()
            current_section = maybe_section
            continue
        buffer.append(line)
        if sum(len(item) for item in buffer) > max_chars:
            flush()
    flush()
    return chunks or [{"section": "General", "text": text[:max_chars]}]


def _section_from_line(line: str) -> str | None:
    normalized = re.sub(r"[^a-z ]", "", line.lower()).strip()
    for hint, section in SECTION_HINTS.items():
        if hint in normalized and len(normalized.split()) <= 4:
            return section
    if line.isupper() and 2 <= len(line.split()) <= 4:
        return line.title()
    return None


def _split_long_chunk(section: str, text: str, max_chars: int) -> list[dict[str, str]]:
    if len(text) <= max_chars:
        return [{"section": section, "text": text}]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[dict[str, str]] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars and current:
            chunks.append({"section": section, "text": current.strip()})
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append({"section": section, "text": current.strip()})
    return chunks


def summarize_cv(text: str, chunks: list[dict[str, str]]) -> dict:
    skills_chunk = next((chunk["text"] for chunk in chunks if chunk["section"] == "Skills"), "")
    return {
        "character_count": len(text),
        "sections": sorted({chunk["section"] for chunk in chunks}),
        "skills_preview": skills_chunk[:600],
    }

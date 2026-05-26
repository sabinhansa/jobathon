from app.services.cv_parser import chunk_cv, clean_text, sanitize_filename, summarize_cv, text_hash


def test_sanitize_filename_removes_path_and_bad_chars():
    assert sanitize_filename("../my<cv>.txt") == "my_cv_.txt"


def test_clean_text_collapses_spacing():
    assert clean_text("A   B\r\n\r\n\r\nC") == "A B\n\nC"


def test_chunk_cv_detects_sections():
    text = """
SUMMARY
Full-stack engineer building Python APIs.

SKILLS
Python, FastAPI, React, Docker

EXPERIENCE
Built local-first AI tools.
"""
    chunks = chunk_cv(text, max_chars=80)
    sections = {chunk["section"] for chunk in chunks}
    assert "Summary" in sections
    assert "Skills" in sections
    assert "Experience" in sections
    assert summarize_cv(text, chunks)["sections"]
    assert len(text_hash(text)) == 64


import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SAFE_FILES = [
    ROOT / "src" / "llm_platform_starter" / "evals" / "fixtures" / "ticket_classification.jsonl",
    ROOT / "src" / "llm_platform_starter" / "prompts" / "templates" / "ticket_classifier.json",
]
PRIVATE_IDENTIFIER_PATTERNS = {
    "email address": re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "US SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit card-like number": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "North American phone number": re.compile(r"\b(?:\+?1[ -.])?\(?\d{3}\)?[ -.]?\d{3}[ -.]?\d{4}\b"),
}


def _load_text(path: Path) -> str:
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        return json.dumps(rows)
    if path.suffix == ".json":
        return json.dumps(json.loads(path.read_text(encoding="utf-8")))
    return path.read_text(encoding="utf-8")


def test_public_safe_fixture_text_avoids_private_identifiers():
    scanned_text = "\n".join(_load_text(path) for path in PUBLIC_SAFE_FILES)

    for label, pattern in PRIVATE_IDENTIFIER_PATTERNS.items():
        assert not pattern.search(scanned_text), f"Found {label} in public-safe fixture text"

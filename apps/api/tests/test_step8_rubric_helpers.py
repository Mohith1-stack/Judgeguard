import ast
from pathlib import Path


def test_step8_files_parse():
    files = [
        Path("app/api/judging.py"),
        Path("app/schemas/judging.py"),
        Path("app/services/rubrics.py"),
    ]
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

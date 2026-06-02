from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse


MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
README_PATH = "../README.md"


def iter_markdown_files(project_root: str | Path) -> list[Path]:
    """Return tracked-style markdown files, excluding generated/vendor directories."""

    root = Path(project_root)
    excluded_parts = {".git", ".venv", "dbt/target", "dbt/dbt_packages"}
    files = []
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        if any(str(relative).startswith(part) for part in excluded_parts):
            continue
        files.append(path)
    return sorted(files)


def extract_local_links(markdown_text: str) -> list[str]:
    """Extract non-HTTP markdown links from a markdown document."""

    links = []
    for raw_link in MARKDOWN_LINK_PATTERN.findall(markdown_text):
        link = raw_link.strip()
        if not link or link.startswith("#"):
            continue
        parsed = urlparse(link)
        if parsed.scheme in {"http", "https", "mailto"}:
            continue
        links.append(link)
    return links


def resolve_markdown_link(markdown_file: Path, link: str) -> Path:
    """Resolve a markdown local link relative to the markdown file."""

    path_part = link.split("#", 1)[0]
    path_part = unquote(path_part)
    return (markdown_file.parent / path_part).resolve()


def validate_markdown_links(project_root: str | Path) -> list[dict[str, str]]:
    """Validate local links in markdown docs point to existing files."""

    failures = []
    root = Path(project_root).resolve()
    for markdown_file in iter_markdown_files(root):
        text = markdown_file.read_text(encoding="utf-8")
        for link in extract_local_links(text):
            path_part = link.split("#", 1)[0]
            if not path_part:
                continue
            target = resolve_markdown_link(markdown_file, link)
            if not target.exists():
                failures.append(
                    {
                        "file": str(markdown_file.relative_to(root)),
                        "link": link,
                        "resolved_path": str(target),
                    }
                )
    return failures


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    failures = validate_markdown_links(project_root)
    if failures:
        formatted = "\n".join(
            f"{failure['file']}: {failure['link']} -> {failure['resolved_path']}"
            for failure in failures
        )
        raise SystemExit(f"Broken markdown links found:\n{formatted}")
    print("Markdown link validation passed.")


if __name__ == "__main__":
    main()

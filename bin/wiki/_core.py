"""Local wiki link checks; adapted from the PDLC donor (MIT)."""
from __future__ import annotations

import json

import re

import sys


from dataclasses import dataclass

from pathlib import Path

from urllib.parse import unquote, urlsplit

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")

REFERENCE_DEFINITION_RE = re.compile(r"^ {0,3}\[((?:\\.|[^\]\\])+)\]:[ \t]*(.+)$")

REFERENCE_LINK_RE = re.compile(
    r"(?<!\\)!?\[((?:\\.|[^\]\\\n])+)\](?:[ \t]*\[((?:\\.|[^\]\\\n])*)\])?"
)

INLINE_CODE_RE = re.compile(r"(`+)(.*?)\1")

WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")

FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")

class WikiError(RuntimeError):
    """Контролируемая ошибка вызова harness."""

@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: Path
    message: str
    line: int | None = None

    def sort_key(self, root: Path) -> tuple[str, str, int, str]:
        return (
            self.severity,
            relative_path(self.path, root),
            self.line or 0,
            self.code,
        )

    def render(self, root: Path) -> str:
        location = relative_path(self.path, root)
        if self.line is not None:
            location = f"{location}:{self.line}"
        label = "ОШИБКА" if self.severity == "error" else "ПРЕДУПРЕЖДЕНИЕ"
        return f"{label} {self.code} {location}: {self.message}"

@dataclass(frozen=True)
class LinkReference:
    source: Path
    line: int
    destination: str
    target: Path | None
    finding: Finding | None

def relative_path(path: Path, root: Path) -> str:
    try:
        return path.absolute().relative_to(root.absolute()).as_posix()
    except ValueError:
        return path.as_posix()

def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

def without_code_lines(text: str, *, preserve_inline: bool = False) -> list[str]:
    result: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    fence_indent = 0
    indented_code = False
    paragraph = False
    list_indents: list[int] = []

    for line in text.splitlines():
        expanded = line.expandtabs(4)
        indent = len(expanded) - len(expanded.lstrip(' '))
        if fence_character is not None:
            fence = FENCE_RE.match(expanded[fence_indent:] if indent >= fence_indent else expanded)
            if (fence and fence.group(1)[0] == fence_character
                    and len(fence.group(1)) >= fence_length and not fence.group(2).strip()):
                fence_character = None
                fence_length = 0
            result.append('')
            continue

        if not line.strip():
            result.append('')
            paragraph = False
            continue

        # A continuation is indented relative to its list item, not the page.
        # Four spaces can therefore be ordinary list text, rather than code.
        while list_indents and indent < list_indents[-1]:
            list_indents.pop()
        container_indent = list_indents[-1] if list_indents else 0
        if indent - container_indent >= 4 and (indented_code or not paragraph):
            result.append('')
            indented_code = True
            continue
        indented_code = False

        marker = re.match(r"^ *(?:[-+*]|\d{1,9}[.)]) +(?=\S)", expanded)
        if marker and indent - container_indent < 4:
            list_indents.append(marker.end())
            paragraph = True
        content_line = expanded[container_indent:]
        fence = FENCE_RE.match(content_line)
        if fence:
            marker = fence.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            fence_indent = container_indent
            paragraph = False
            result.append('')
            continue

        # An indented block cannot interrupt a prose paragraph. Headings,
        # reference definitions and separators end that paragraph instead.
        paragraph = not bool(re.match(
            r"^ {0,3}(?:#{1,6}(?:\s|$)|\[[^\]]+\]:|(?:[-*_] *){3,}$)", content_line
        ))
        result.append(line if preserve_inline else INLINE_CODE_RE.sub("", line))

    return result

def link_destination(raw_destination: str) -> str:
    destination = raw_destination.strip()
    if destination.startswith("<") and ">" in destination:
        return destination[1 : destination.index(">")]
    return destination.split(maxsplit=1)[0]

def iter_link_destinations(path: Path) -> list[tuple[int, str]]:
    destinations: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8")
    # Definitions retain quoted titles and inline code in file names; usages
    # exclude inline code. Both passes retain the original source line numbers.
    definition_lines = without_code_lines(text, preserve_inline=True)
    definitions: dict[str, str] = {}
    excluded: set[int] = set()
    for line_number, line in enumerate(definition_lines, start=1):
        match = REFERENCE_DEFINITION_RE.match(line)
        if match:
            label = normalized_reference_label(match.group(1))
            definitions.setdefault(label, link_destination(match.group(2)))
            excluded.add(line_number)
    for line_number, line in enumerate(without_code_lines(text), start=1):
        if line_number in excluded:
            continue
        inline_spans = []
        for match in LINK_RE.finditer(line):
            destinations.append((line_number, link_destination(match.group(1))))
            inline_spans.append(match.span())
        for match in REFERENCE_LINK_RE.finditer(line):
            if any(start < match.end() and match.start() < end for start, end in inline_spans):
                continue
            label = normalized_reference_label(match.group(2) or match.group(1))
            if label in definitions:
                destinations.append((line_number, definitions[label]))
    return destinations

def normalized_reference_label(label: str) -> str:
    label = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])", r"\1", label)
    return " ".join(label.casefold().split())

def resolve_link(root: Path, source: Path, line: int, destination: str) -> LinkReference:
    if not destination or destination.startswith("#"):
        return LinkReference(source, line, destination, None, None)

    if (
        destination.startswith("/")
        or WINDOWS_ABSOLUTE_RE.match(destination)
    ):
        finding = Finding(
            "error",
            "E_LINK_ABSOLUTE",
            source,
            f"абсолютная локальная ссылка запрещена: {destination}",
            line,
        )
        return LinkReference(source, line, destination, None, finding)

    parsed = urlsplit(destination)
    scheme = parsed.scheme.casefold()
    if (scheme and scheme != "file") or destination.startswith("//"):
        return LinkReference(source, line, destination, None, None)

    if scheme == "file":
        finding = Finding(
            "error",
            "E_LINK_ABSOLUTE",
            source,
            f"абсолютная локальная ссылка запрещена: {destination}",
            line,
        )
        return LinkReference(source, line, destination, None, finding)

    target_text = unquote(parsed.path).replace("\\ ", " ")
    if not target_text:
        return LinkReference(source, line, destination, None, None)

    candidate = source.parent / target_text
    resolved_root = root.resolve()
    resolved_target = candidate.resolve(strict=False)
    if not is_within(resolved_target, resolved_root):
        finding = Finding(
            "error",
            "E_LINK_ESCAPE",
            source,
            f"локальная ссылка выходит за границу репозитория: {destination}",
            line,
        )
        return LinkReference(source, line, destination, None, finding)

    if not candidate.exists():
        finding = Finding(
            "error",
            "E_LINK_MISSING",
            source,
            f"цель не существует: {destination}",
            line,
        )
        return LinkReference(source, line, destination, resolved_target, finding)

    if resolved_target.is_dir():
        readme = resolved_target / "README.md"
        if readme.is_file():
            resolved_target = readme.resolve()
            if not is_within(resolved_target, resolved_root):
                finding = Finding('error', 'E_LINK_ESCAPE', source,
                                  f'README каталога выходит за границу проекта: {destination}', line)
                return LinkReference(source, line, destination, None, finding)

    return LinkReference(source, line, destination, resolved_target, None)

def link_references(root: Path, files: list[Path] | None = None) -> list[LinkReference]:
    references: list[LinkReference] = []
    for source in files or markdown_files(root):
        for line, destination in iter_link_destinations(source):
            references.append(resolve_link(root, source, line, destination))
    return references

def link_findings(root: Path) -> list[Finding]:
    findings = unsafe_markdown_findings(root)
    findings.extend(
        reference.finding
        for reference in link_references(root)
        if reference.finding is not None
    )
    return findings

def affected_documents(root: Path, query: str) -> dict[Path, set[str]]:
    query_path = Path(query)
    candidate = query_path if query_path.is_absolute() else root / query_path
    path_mode = candidate.exists()
    target: Path | None = None
    relative_query = ""
    basename = ""
    stem = ""

    if path_mode:
        target = candidate.resolve()
        if not is_within(target, root.resolve()):
            raise WikiError("указанный путь выходит за границу репозитория")
        relative_query = target.relative_to(root.resolve()).as_posix().casefold()
        basename = target.name.casefold()
        stem = target.stem.casefold()

    matches: dict[Path, set[str]] = {}
    for source in markdown_files(root):
        if target is not None and source.resolve() == target:
            continue
        text = source.read_text(encoding="utf-8")
        folded = text.casefold()
        types: set[str] = set()

        if target is not None:
            for reference in link_references(root, [source]):
                if (
                    reference.finding is None
                    and reference.target is not None
                    and reference.target.resolve() == target
                ):
                    types.add("прямая-ссылка")
            if relative_query and relative_query in folded:
                types.add("путь")
            if basename and basename in folded:
                types.add("имя-файла")
            if stem and stem != basename and stem in folded:
                types.add("основа-имени")
        elif query.casefold() in folded:
            types.add("фраза")

        if types:
            matches[source] = types

    return dict(sorted(matches.items(), key=lambda item: relative_path(item[0], root)))


def discover_repository(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if start is not None:
        candidates = (current,)
    else:
        candidates = (current, *current.parents)
    for root in candidates:
        if (root / 'knowledge').is_dir():
            for name in ('raw', 'knowledge'):
                if (root / name).is_symlink():
                    raise WikiError(f'Корень {name} не должен быть symlink')
            return root
        if (root / '.git').exists() or (root / 'skill-version.json').exists():
            break
    raise WikiError('Не найден knowledge/ в выбранном проекте; используйте --project PATH')


def candidate_markdown_files(root: Path) -> list[Path]:
    files = {root / name for name in ('README.md', 'AGENTS.md') if (root / name).is_file()}
    for name in ('raw', 'knowledge'):
        directory = root / name
        if directory.is_dir():
            files.update(path for path in directory.rglob('*.md') if path.is_file() or path.is_symlink())
    return sorted(files)


def markdown_files(root: Path) -> list[Path]:
    return [path for path in candidate_markdown_files(root)
            if path.is_file() and is_within(path.resolve(), root.resolve())]


def unsafe_markdown_findings(root: Path) -> list[Finding]:
    return [Finding('error', 'E_FILE_ESCAPE', path, 'Markdown symlink выходит за пределы проекта')
            for path in candidate_markdown_files(root) if not is_within(path.resolve(), root.resolve())]


def orphan_pages(root: Path) -> list[Path]:
    pages = [p for p in markdown_files(root) if p.is_relative_to(root / 'knowledge')]
    inbound = {ref.target for ref in link_references(root) if ref.finding is None
               and ref.target is not None and ref.target != ref.source.resolve()}
    supporting = {'index.md', 'SCHEMA.md', 'README.md', 'GLOSSARY.md', 'log.md'}
    return [p for p in pages if p.resolve() not in inbound
            and not (p.parent == root / 'knowledge' and p.name in supporting)]


def lint_findings(root: Path) -> list[Finding]:
    findings = link_findings(root)
    index = root / 'knowledge/index.md'
    if not index.is_file():
        findings.append(Finding('error', 'E_INDEX_MISSING', index, 'Нет входной страницы knowledge/index.md'))
    for name, code in (('GLOSSARY.md', 'W_GLOSSARY_MISSING'), ('log.md', 'W_LOG_MISSING')):
        path = root / 'knowledge' / name
        if not path.is_file():
            findings.append(Finding('warning', code, path, f'Нет обязательной страницы knowledge/{name}'))
    findings.extend(Finding('warning', 'W_ORPHAN', p, 'Нет входящих ссылок') for p in orphan_pages(root))
    return sorted(findings, key=lambda f: f.sort_key(root))


def main(command: str) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Read-only local wiki checks; no network requests')
    parser.add_argument('--project', type=Path, help='corpus root containing raw/ and knowledge/')
    parser.add_argument('--json', action='store_true')
    if command == 'lint':
        parser.add_argument('--dry-run', action='store_true', help='explicit read-only mode (default)')
    if command == 'affected':
        parser.add_argument('query', help='existing source path or text phrase')
    args = parser.parse_args()
    try:
        root = discover_repository(args.project)
        if command == 'lint':
            findings = lint_findings(root)
            errors = sum(f.severity == 'error' for f in findings)
            result = {'findings': [dict(severity=f.severity, code=f.code, path=relative_path(f.path, root),
                                        line=f.line, message=f.message) for f in findings],
                      'errors': errors, 'warnings': len(findings) - errors}
            lines = [f.render(root) for f in findings]
            lines.append(f'Итог: {errors} блокирующих ошибок, {len(findings) - errors} предупреждений.')
            code = 1 if errors else 0
        elif command == 'status':
            files = markdown_files(root)
            result = {'knowledge_pages': sum(p.is_relative_to(root / 'knowledge') for p in files),
                      'raw_pages': sum(p.is_relative_to(root / 'raw') for p in files),
                      'link_errors': len(link_findings(root)), 'orphans': len(orphan_pages(root))}
            lines = [f'{key}: {value}' for key, value in result.items()]
            code = 0
        elif command == 'find-orphans':
            result = {'orphans': [relative_path(p, root) for p in orphan_pages(root)]}
            lines = ['Страницы-сироты: ' + str(len(result['orphans'])), *result['orphans']]
            code = 0
        else:
            if not args.query.strip():
                raise WikiError('Нужен непустой путь или текст')
            matches = affected_documents(root, args.query)
            result = {'matches': {relative_path(p, root): sorted(kinds) for p, kinds in matches.items()}}
            lines = [f'[{", ".join(kinds)}] {path}' for path, kinds in result['matches'].items()]
            code = 0
        result['limitations'] = ['Локальные пути, без проверки якорей, внешних URL и истинности утверждений.']
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else '\n'.join(lines))
        return code
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        if args.json:
            print(json.dumps({'error': str(error)}, ensure_ascii=False))
        else:
            print(f'Ошибка wiki-инструмента: {error}', file=sys.stderr)
        return 2

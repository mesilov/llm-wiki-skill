"""Read-only provenance checks for the minimal raw envelope."""
import argparse
import json
import re
from datetime import date
from pathlib import Path

from _core import WikiError, discover_repository, relative_path

UNIT = re.compile(r'(\d{4}-\d{2}-\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', type=Path, help='unit directories or README.md paths relative to cwd')
    parser.add_argument('--project', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    findings, checked = [], []

    def finding(code, path, message, severity='error'):
        findings.append(dict(code=code, path=relative_path(path, root), message=message, severity=severity))

    try:
        root = discover_repository(args.project)
        raw = root / 'raw'
        if not raw.is_dir():
            raise WikiError('Нет каталога raw/')
        units = []
        if args.paths:
            for path in args.paths:
                path = path.absolute()
                units.append(path if path.name == 'README.md' else path / 'README.md')
        else:
            for entry in sorted(raw.iterdir()):
                if entry.name in {'README.md', 'index.md'}:
                    continue
                if entry.is_symlink():
                    finding('E_RAW_PATH', entry, 'Symlink не проверяется')
                elif entry.is_dir():
                    units.append(entry / 'README.md')
                else:
                    finding('W_RAW_UNSCANNED', entry, 'Файл вне единицы источника; не проверен', 'warning')
        if units:
            try:
                import yaml
            except ImportError as error:
                raise WikiError('raw-lint требует PyYAML; установите bin/wiki/requirements.txt') from error
            class UniqueSafeLoader(yaml.SafeLoader):
                def construct_mapping(self, node, deep=False):
                    self.flatten_mapping(node)
                    keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
                    if any(not isinstance(key, str) for key in keys):
                        raise ValueError('Ключи метаданных должны быть строками')
                    if len(set(keys)) != len(keys):
                        raise ValueError('Повторяющийся ключ YAML')
                    return super().construct_mapping(node, deep=deep)
        for path in sorted(set(units)):
            if not path.is_relative_to(raw) or not path.resolve().is_relative_to(raw.resolve()):
                finding('E_RAW_PATH', path, 'Источник вне raw/')
                continue
            if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(raw)):
                finding('E_RAW_PATH', path, 'Symlink не проверяется')
                continue
            match = UNIT.fullmatch(path.parent.name)
            valid = path.parent.parent == raw and bool(match)
            if match:
                try:
                    date.fromisoformat(match[1])
                except ValueError:
                    valid = False
            if not valid:
                finding('E_RAW_TREE', path, 'Ожидается raw/YYYY-MM-DD-slug/README.md; существующий корпус не мигрируется')
                continue
            if not path.is_file():
                finding('E_RAW_ROOT', path, 'Нет README.md источника')
                continue
            checked.append(relative_path(path, root))
            lines = path.read_text(encoding='utf-8').splitlines()
            try:
                if not lines or lines[0] != '---':
                    raise ValueError('Нет YAML frontmatter')
                end = lines.index('---', 1)
                metadata = yaml.load('\n'.join(lines[1:end]), Loader=UniqueSafeLoader)
                if not isinstance(metadata, dict):
                    raise ValueError('Метаданные должны быть объектом')
            except (ValueError, yaml.YAMLError) as error:
                finding('E_RAW_YAML', path, str(error))
                continue
            if not isinstance(metadata.get('source'), str) or not metadata['source'].strip():
                finding('E_RAW_SOURCE', path, 'Нужно непустое source: URL или описание происхождения')
            retrieved = str(metadata.get('retrieved', ''))
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', retrieved):
                    raise ValueError()
                date.fromisoformat(retrieved)
            except ValueError:
                finding('E_RAW_DATE', path, 'retrieved: реальная дата YYYY-MM-DD')
        errors = sum(f['severity'] == 'error' for f in findings)
        report = {'checked': checked, 'findings': findings,
                  'summary': {'checked': len(checked), 'errors': errors, 'warnings': len(findings) - errors}}
        code = 1 if errors else 0
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        report = {'error': str(error), 'checked': checked, 'findings': findings}
        code = 2
    report['limitations'] = ['Проверены только локальные envelopes; содержимое источников, свежесть и внешние URL не проверены.']
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else
          '\n'.join([f"{f['code']} {f['path']}: {f['message']}" for f in findings]
                    + [str(report.get('error', report.get('summary')))]))
    return code

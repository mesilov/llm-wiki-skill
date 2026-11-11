import subprocess

import sys

import tempfile

import unittest

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BIN_DIR = PROJECT_ROOT / "bin" / "wiki"

class WikiCliTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary_directory.name)
        self.root = temporary_root / "repository"
        self.root.mkdir()
        (self.root / ".git").mkdir()
        for directory in ("raw", "knowledge", "openspec"):
            (self.root / directory).mkdir()
        (self.root / "README.md").write_text("# Проект\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("# Инструкции\n", encoding="utf-8")
        self.write("knowledge/index.md", "# Wiki\n")
        self.write("knowledge/GLOSSARY.md", "# Глоссарий\n\n## Видео\n\nВидеоматериал.\n")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_cli(self, command: str, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(BIN_DIR / command), *arguments],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

class LinkLintTest(WikiCliTestCase):
    def test_accepts_existing_relative_link(self):
        self.write("knowledge/target.md", "# Цель\n")
        self.write("knowledge/source.md", "[Цель](target.md)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("блокирующих ошибок", result.stdout)

    def test_reports_broken_relative_link_with_source_line(self):
        self.write("knowledge/source.md", "Первая строка\n[Нет](missing.md)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 1)
        self.assertIn("E_LINK_MISSING", result.stdout)
        self.assertIn("knowledge/source.md:2", result.stdout)

    def test_accepts_fragment_only_anchor(self):
        self.write("knowledge/source.md", "# Раздел\n[Выше](#раздел)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_accepts_external_url(self):
        self.write("knowledge/source.md", "[Источник](https://example.com/a#b)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_accepts_angle_bracket_path_with_spaces(self):
        self.write("knowledge/path with spaces.md", "# Пробелы\n")
        self.write("knowledge/source.md", "[Файл](<path with spaces.md>)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_accepts_percent_encoded_path_with_spaces(self):
        self.write("knowledge/path with spaces.md", "# Пробелы\n")
        self.write("knowledge/source.md", "[Файл](path%20with%20spaces.md)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_accepts_nested_relative_link(self):
        self.write("knowledge/domains/source/overview.md", "[Цель](../target/page.md)\n")
        self.write("knowledge/domains/target/page.md", "# Цель\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_lexical_path_escape(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("# Снаружи\n", encoding="utf-8")
        self.write("knowledge/source.md", "[Снаружи](../../outside.md)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 1)
        self.assertIn("E_LINK_ESCAPE", result.stdout)

    def test_rejects_symlink_path_escape(self):
        outside = self.root.parent / "outside.md"
        outside.write_text("# Снаружи\n", encoding="utf-8")
        link = self.root / "knowledge" / "outside-link.md"
        link.symlink_to(outside)
        self.write("knowledge/source.md", "[Снаружи](outside-link.md)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 1)
        self.assertIn("E_LINK_ESCAPE", result.stdout)

    def test_rejects_windows_absolute_local_path(self):
        self.write("knowledge/source.md", "[Локальный файл](C:\\temp\\file.md)\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 1)
        self.assertIn("E_LINK_ABSOLUTE", result.stdout)

    def test_ignores_link_example_inside_fenced_code(self):
        self.write("knowledge/source.md", "```markdown\n[Пример](missing.md)\n```\n")

        result = self.run_cli("lint")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reports_broken_reference_link_at_usage_line(self):
        self.write('knowledge/source.md',
                   '# Source\n\n[Нет][source]\n\n[source]: missing.md\n')
        result = self.run_cli('lint')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('E_LINK_MISSING knowledge/source.md:3', result.stdout)

    def test_reference_links_share_path_safety_checks(self):
        for destination, code in (('/outside.md', 'E_LINK_ABSOLUTE'),
                                  ('../../outside.md', 'E_LINK_ESCAPE')):
            with self.subTest(destination=destination):
                self.write('knowledge/source.md',
                           f'[Источник][ref]\n\n[ref]: {destination}\n')
                result = self.run_cli('lint')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(code, result.stdout)

    def test_reference_links_reach_index_orphans_and_affected(self):
        self.write('knowledge/domains/topic/page.md', '# Topic\n')
        self.write('knowledge/index.md',
                   '[Topic][ MAIN   page ]\n\n[main page]: <domains/topic/page.md> "Title"\n')
        lint = self.run_cli('lint')
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)
        self.assertNotIn('W_INDEX_MISSING', lint.stdout)
        self.assertNotIn('knowledge/domains/topic/page.md', self.run_cli('find-orphans').stdout)
        affected = self.run_cli('affected', 'knowledge/domains/topic/page.md')
        self.assertIn('прямая-ссылка', affected.stdout)
        self.assertIn('knowledge/index.md', affected.stdout)

    def test_collapsed_shortcut_and_image_references_are_checked(self):
        for usage in ('[ref][]', '[ref]', '![alt][ref]'):
            with self.subTest(usage=usage):
                self.write('knowledge/source.md', f'{usage}\n\n[ref]: missing.md\n')
                result = self.run_cli('lint')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('E_LINK_MISSING', result.stdout)

    def test_ignores_reference_definitions_and_uses_first_duplicate(self):
        self.write('knowledge/target.md', '# Target\n')
        self.write('knowledge/source.md',
                   '[ref]\n\n[ref]: target.md\n[REF]: missing.md\n[unused]: missing.md\n')
        result = self.run_cli('lint')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ignores_references_inside_inline_and_fenced_code(self):
        self.write('knowledge/source.md',
                   '`[ref]`\n\n```md\n[ref]\n```\n\n[ref]: missing.md\n')
        result = self.run_cli('lint')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ignores_link_examples_inside_indented_code(self):
        for indent in ('    ', '\t'):
            with self.subTest(indent=repr(indent)):
                self.write('knowledge/source.md',
                           f'# Source\n\n{indent}[Пример](missing.md)\n\n{indent}[ref]\n\n[ref]: missing.md\n')
                result = self.run_cli('lint')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_indented_paragraph_continuation_is_still_checked(self):
        self.write('knowledge/source.md', 'Paragraph\n    [Нет](missing.md)\n')
        result = self.run_cli('lint')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('knowledge/source.md:2', result.stdout)

    def test_indented_list_continuation_is_still_checked(self):
        self.write('knowledge/source.md', '- Item\n\n    [Нет](missing.md)\n')
        result = self.run_cli('lint')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('knowledge/source.md:3', result.stdout)

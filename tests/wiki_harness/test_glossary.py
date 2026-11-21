import json

import shutil

from tests.wiki_harness.test_cli import PROJECT_ROOT, WikiCliTestCase

GLOSSARY = "knowledge/GLOSSARY.md"


class GlossaryLintTest(WikiCliTestCase):
    def glossary(self, text: str):
        return self.write(GLOSSARY, text)

    def findings(self, *codes: str) -> list[dict]:
        result = self.run_cli("lint", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        return [f for f in data["findings"] if f["code"] in codes]

    def glossary_findings(self) -> list[tuple[str, int]]:
        found = self.findings("W_GLOSSARY_DUPLICATE", "W_GLOSSARY_EMPTY")
        for finding in found:
            self.assertEqual(finding["path"], GLOSSARY)
            self.assertEqual(finding["severity"], "warning")
        return [(f["code"], f["line"]) for f in found]

    def test_duplicate_with_different_case_and_spaces(self):
        self.glossary("# Глоссарий\n\n## ASR\n\nРечь.\n\n##   asr  \n\nДругое.\n")
        self.assertEqual(self.glossary_findings(), [("W_GLOSSARY_DUPLICATE", 7)])

    def test_inline_code_and_closing_hashes_do_not_hide_duplicate(self):
        self.glossary("# Глоссарий\n\n## `ASR`\n\nРечь.\n\n## asr ##\n\nДругое.\n")
        self.assertEqual(self.glossary_findings(), [("W_GLOSSARY_DUPLICATE", 7)])

    def test_distinct_qualified_titles_are_not_duplicates(self):
        self.glossary(
            "# Глоссарий\n\n## Решение (`Decision`)\n\nВыбор.\n\n"
            "## Решение (`Verdict`)\n\nДействие.\n"
        )
        self.assertEqual(self.glossary_findings(), [])

    def test_empty_entry_in_the_middle(self):
        self.glossary("# Глоссарий\n\n## А\n\nА.\n\n## Б\n\n\n## В\n\nВ.\n")
        self.assertEqual(self.glossary_findings(), [("W_GLOSSARY_EMPTY", 7)])

    def test_empty_entry_at_the_end(self):
        for ending in ("## Б", "## Б\n", "## Б\n\n   \n"):
            with self.subTest(ending=ending):
                self.glossary("# Глоссарий\n\n## А\n\nА.\n\n" + ending)
                self.assertEqual(self.glossary_findings(), [("W_GLOSSARY_EMPTY", 7)])

    def test_heading_without_title_is_empty(self):
        self.glossary("# Глоссарий\n\n##\n\nТекст.\n")
        self.assertEqual(self.glossary_findings(), [("W_GLOSSARY_EMPTY", 3)])

    def test_avoid_context_and_subheadings_alone_are_not_a_definition(self):
        self.glossary(
            "# Глоссарий\n\n## Анализ\n\n"
            "_Avoid_: исследование — другое понятие;\n"
            "проверка — неоднозначно.\n\n"
            "**Контекст:** [Схема](index.md).\n\n"
            "### Детали\n\n"
            "<!-- черновик\nбез текста -->\n\n---\n"
        )
        self.assertEqual(self.glossary_findings(), [("W_GLOSSARY_EMPTY", 3)])

    def test_definition_with_avoid_and_context_is_not_empty(self):
        self.glossary(
            "# Глоссарий\n\n## Анализ\n\n"
            "_Avoid_: исследование — другое понятие.\n\n"
            "Разбор материала на части.\n\n"
            "**Контекст:** [Схема](index.md).\n"
        )
        self.assertEqual(self.glossary_findings(), [])

    def test_inline_code_and_code_block_are_definition_text(self):
        self.glossary("# Глоссарий\n\n## Verdict\n\n`skip`\n\n## Схема\n\n```json\n{}\n```\n")
        self.assertEqual(self.glossary_findings(), [])

    def test_heading_inside_code_block_is_not_an_entry(self):
        self.glossary(
            "# Глоссарий\n\n## Пример\n\nОбразец записи:\n\n"
            "```md\n## Пример\n\n```\n\n~~~\n## Пустая\n~~~\n"
        )
        self.assertEqual(self.glossary_findings(), [])

    def test_frontmatter_is_skipped(self):
        self.glossary(
            "---\ntitle: Глоссарий\nnotes: |\n  ## Не запись\n---\n"
            "# Глоссарий\n\n## А\n\nА.\n\n## а\n\nДругое.\n\n## Б\n"
        )
        self.assertEqual(
            self.glossary_findings(),
            [("W_GLOSSARY_DUPLICATE", 12), ("W_GLOSSARY_EMPTY", 16)],
        )

    def test_frontmatter_alone_does_not_hide_entries_after_unclosed_block(self):
        self.glossary("---\n## А\n\nА.\n\n## а\n\nДругое.\n")
        self.assertEqual(self.glossary_findings(), [("W_GLOSSARY_DUPLICATE", 6)])

    def test_crlf_lines(self):
        path = self.root / GLOSSARY
        path.write_bytes(b"# Glossary\r\n\r\n## ASR\r\n\r\nA.\r\n\r\n## asr\r\n\r\n## B\r\n\r\nB.\r\n")
        self.assertEqual(
            self.glossary_findings(),
            [("W_GLOSSARY_DUPLICATE", 7), ("W_GLOSSARY_EMPTY", 7)],
        )

    def test_missing_glossary_only_reports_missing(self):
        (self.root / GLOSSARY).unlink()
        self.assertEqual(self.glossary_findings(), [])
        self.assertEqual(len(self.findings("W_GLOSSARY_MISSING")), 1)
        self.assertFalse((self.root / GLOSSARY).exists())

    def test_file_without_entries_is_not_reported(self):
        self.glossary("# Глоссарий\n\nСвой формат: термины списком.\n\n- А — буква.\n")
        self.assertEqual(self.glossary_findings(), [])

    def test_template_glossary_has_no_findings(self):
        shutil.copyfile(PROJECT_ROOT / "templates/wiki/knowledge/GLOSSARY.md", self.root / GLOSSARY)
        self.write("knowledge/SCHEMA.md", "# Схема\n")
        self.assertEqual(self.glossary_findings(), [])

    def test_dry_run_reports_location_and_does_not_write(self):
        path = self.glossary("# Глоссарий\n\n## А\n\nА.\n\n## а\n\n")
        before = path.read_bytes()
        modified = path.stat().st_mtime_ns
        result = self.run_cli("lint", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("W_GLOSSARY_DUPLICATE knowledge/GLOSSARY.md:7", result.stdout)
        self.assertIn("W_GLOSSARY_EMPTY knowledge/GLOSSARY.md:7", result.stdout)
        self.assertIn("строки 3", result.stdout)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_mtime_ns, modified)

    def test_exit_code_still_reflects_only_errors(self):
        self.glossary("# Глоссарий\n\n## А\n\n## а\n\n[Нет](missing.md)\n")
        result = self.run_cli("lint")
        self.assertEqual(result.returncode, 1)
        self.assertIn("W_GLOSSARY_EMPTY knowledge/GLOSSARY.md:3", result.stdout)
        self.assertIn("W_GLOSSARY_DUPLICATE knowledge/GLOSSARY.md:5", result.stdout)

    def test_glossary_symlink_outside_project_is_not_read(self):
        target = self.root.parent / "outside.md"
        target.write_text("# Глоссарий\n\n## А\n\n## а\n", encoding="utf-8")
        path = self.root / GLOSSARY
        path.unlink()
        path.symlink_to(target)
        result = self.run_cli("lint", "--json")
        data = json.loads(result.stdout)
        codes = {f["code"] for f in data["findings"]}
        self.assertIn("E_FILE_ESCAPE", codes)
        self.assertNotIn("W_GLOSSARY_DUPLICATE", codes)
        self.assertNotIn("W_GLOSSARY_EMPTY", codes)

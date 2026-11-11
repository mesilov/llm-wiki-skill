import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[2] / 'bin/wiki'
requires_yaml = unittest.skipUnless(importlib.util.find_spec('yaml'),
                                    'raw-lint требует PyYAML из bin/wiki/requirements.txt')


class MinimalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'raw').mkdir()
        (self.root / 'knowledge').mkdir()
        (self.root / 'knowledge/index.md').write_text('# Wiki\n')

    def run_cli(self, command, *args, cwd=None):
        return subprocess.run([sys.executable, str(BIN / command), *args],
                              cwd=cwd or self.root, capture_output=True, text=True)

    def test_no_config_or_schema_required_for_read_only_checks(self):
        before = list(self.root.rglob('*'))
        for name in ('lint', 'status', 'find-orphans', 'raw-lint'):
            result = self.run_cli(name, '--json')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            json.loads(result.stdout)
        self.assertEqual(before, list(self.root.rglob('*')))

    def test_missing_index_and_orphan_are_reported(self):
        (self.root / 'knowledge/index.md').unlink()
        (self.root / 'knowledge/topic.md').write_text('# Topic\n')
        result = self.run_cli('lint', '--json')
        self.assertEqual(result.returncode, 1, result.stderr)
        codes = {f['code'] for f in json.loads(result.stdout)['findings']}
        self.assertTrue({'E_INDEX_MISSING', 'W_ORPHAN'} <= codes)

    def test_nested_git_boundary_does_not_read_parent_wiki(self):
        child = self.root / 'nested'
        (child / '.git').mkdir(parents=True)
        result = self.run_cli('status', cwd=child)
        self.assertEqual(result.returncode, 2)

    def test_explicit_root_from_another_directory(self):
        result = self.run_cli('status', '--project', str(self.root), '--json', cwd=self.root.parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['knowledge_pages'], 1)

    def test_unsafe_markdown_is_not_read(self):
        with tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / 'secret.md'
            secret.write_text('secret')
            (self.root / 'knowledge/escape.md').symlink_to(secret)
            result = self.run_cli('lint', '--json')
            self.assertEqual(result.returncode, 1)
            self.assertIn('E_FILE_ESCAPE', result.stdout)
            self.assertNotIn('secret', result.stdout)

    @requires_yaml
    def test_source_units_need_provenance_and_real_date(self):
        unit = self.root / 'raw/2026-11-11-note'
        unit.mkdir()
        readme = unit / 'README.md'
        readme.write_text('---\nsource: "Interview with owner"\nretrieved: 2026-11-11\n---\n# Note\n')
        result = self.run_cli('raw-lint', '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['summary']['checked'], 1)
        readme.write_text('---\nretrieved: "2026-02-30"\n---\n# Note\n')
        result = self.run_cli('raw-lint', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('E_RAW_SOURCE', result.stdout)
        self.assertIn('E_RAW_DATE', result.stdout)

    @requires_yaml
    def test_raw_does_not_execute_yaml(self):
        unit = self.root / 'raw/2026-11-11-note'
        unit.mkdir()
        (unit / 'README.md').write_text('---\nsource: !!python/object/apply:os.system ["touch evil"]\nretrieved: 2026-11-11\n---\n')
        result = self.run_cli('raw-lint', '--json')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse((self.root / 'evil').exists())

    def test_cli_does_not_claim_to_fix_meaning(self):
        result = self.run_cli('lint', '--fix')
        self.assertEqual(result.returncode, 2)

    def test_directory_link_readme_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'note.md'
            target.write_text('private')
            folder = self.root / 'knowledge/folder'
            folder.mkdir()
            (folder / 'README.md').symlink_to(target)
            (self.root / 'knowledge/index.md').write_text('[Folder](folder/)\n')
            result = self.run_cli('lint', '--json')
            self.assertEqual(result.returncode, 1)
            self.assertIn('E_LINK_ESCAPE', result.stdout)

    @requires_yaml
    def test_duplicate_provenance_is_rejected(self):
        unit = self.root / 'raw/2026-11-11-note'
        unit.mkdir()
        (unit / 'README.md').write_text('---\nsource: one\nsource: two\nretrieved: "2026-11-11"\n---\n')
        result = self.run_cli('raw-lint', '--json')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('E_RAW_YAML', result.stdout)

    def test_markdown_named_attachment_directory_is_not_read_as_file(self):
        folder = self.root / 'raw/2026-11-11-repo/example.md'
        folder.mkdir(parents=True)
        for command in ('lint', 'status', 'find-orphans', 'affected'):
            args = ('repo',) if command == 'affected' else ()
            result = self.run_cli(command, *args, '--json')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

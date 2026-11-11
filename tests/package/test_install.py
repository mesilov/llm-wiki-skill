import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_install(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'),
                               str(self.root), *args], capture_output=True, text=True)

    def test_dry_run_writes_nothing(self):
        result = self.run_install('--init-wiki', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_install_all_agents_and_repeat_without_changes(self):
        for agent in ('codex', 'claude', 'opencode'):
            with self.subTest(agent=agent):
                result = self.run_install('--agent', agent, '--init-wiki')
                self.assertEqual(result.returncode, 0, result.stderr)
                manifest = json.loads((self.root / 'skill-version.json').read_text())
                self.assertEqual(manifest['repository'], 'mesilov/llm-wiki-skill')
                self.assertEqual(len(list((self.root / '.agents/skills').glob('*/SKILL.md'))), 4)
                for name, digest in manifest['files'].items():
                    path = self.root / name
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
                    self.assertEqual(path.stat().st_mode & 0o7777, manifest['modes'][name])
                self.assertFalse((self.root / 'wiki.config.json').exists())
                self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertTrue((self.root / '.claude/skills/wiki-query').is_symlink())

    def test_preflight_conflict_does_not_partially_install(self):
        (self.root / 'knowledge').mkdir()
        original = self.root / 'knowledge/index.md'
        original.write_text('user content')
        result = self.run_install('--init-wiki')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(original.read_text(), 'user content')
        self.assertFalse((self.root / '.agents').exists())

    def test_symlink_destination_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / '.agents').symlink_to(outside, target_is_directory=True)
            result = self.run_install()
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_installed_cli_works_outside_source(self):
        result = self.run_install('--init-wiki')
        self.assertEqual(result.returncode, 0, result.stderr)
        for cmd in ('lint', 'status', 'find-orphans', 'raw-lint'):
            run = subprocess.run([str(self.root / 'bin/wiki' / cmd), '--json'], cwd=self.root,
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            json.loads(run.stdout)
        for name in ('GLOSSARY.md', 'log.md'):
            self.assertTrue((self.root / 'knowledge' / name).is_file())
        lint = subprocess.run([str(self.root / 'bin/wiki/lint'), '--json'], cwd=self.root,
                              capture_output=True, text=True)
        self.assertEqual(json.loads(lint.stdout)['findings'], [])

    def test_utr_upstream_hashes(self):
        ref = ROOT / 'skills/wiki-query/references/utr-source'
        manifest = json.loads((ref / 'manifest.json').read_text())
        for name, digest in manifest['files'].items():
            path = ref / manifest.get('local_paths', {}).get(name, name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)

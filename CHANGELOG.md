# Changelog

## Unreleased

## 0.1.0 — 2026-11-11

Первый выпуск. Несовместимых изменений нет. Установки с канала `main`
переходят на релизы командой `bin/wiki/update --channel release`.

- Добавлен локальный навык мейнтейнера. Для изменений закреплены отдельные
  worktree, интеграция фич через `dev` и запись в changelog для каждого MR;
  релизные теги SemVer ставятся на проверенные commit в `main`.
- Первый набор: четыре навыка `wiki-query`, `wiki-ingest`, `wiki-update`,
  `wiki-lint`, общий контракт, формат источников в `raw/` и полный SimpleEn-RU
  с лицензией и manifest.
- CLI `bin/wiki/`: `lint`, `status`, `find-orphans`, `affected`, `raw-lint`,
  `update`. CLI проверяет ссылки и структуру, но не смысл и актуальность знаний.
- Установщик `scripts/install.py` для Codex, Claude Code и OpenCode с флагами
  `--init-wiki`, `--dry-run`, `--channel`. Updater с каналами `main` и `release`
  закрепляет commit SHA, защищает локальные правки, делает backup и откат.
- README описывает установку стабильного релиза с тега и выбор канала updater.
- Тесты `raw-lint` пропускаются без PyYAML, а не падают. Требования: Python 3.10+,
  PyYAML из `bin/wiki/requirements.txt` для `raw-lint`.

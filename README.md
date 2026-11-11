# LLM Wiki Skills

Реализация подхода [LLM Wiki Андрея Карпатого](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) для локальной базы знаний в Markdown. Агент сохраняет оригиналы в `raw/`, связывает и обновляет страницы в `knowledge/`, ведёт глоссарий понятий и журнал значимых изменений знания и отвечает на вопросы со ссылками на материалы wiki.

| Навык | Что делает |
| --- | --- |
| [wiki-query](skills/wiki-query/SKILL.md) | Отвечает на вопросы по wiki без изменения файлов |
| [wiki-ingest](skills/wiki-ingest/SKILL.md) | Сохраняет источник и дополняет связанные страницы |
| [wiki-update](skills/wiki-update/SKILL.md) | Уточняет и перестраивает существующие страницы |
| [wiki-lint](skills/wiki-lint/SKILL.md) | Проверяет структуру и содержание wiki |

## Установка

Нужен Python 3.10+. Запустите из клона этого репозитория, указав путь к существующему каталогу проекта.

```bash
python3 scripts/install.py /path/to/project --init-wiki
```

По умолчанию установка настроена для Codex. Для Claude Code добавьте `--agent claude`, для OpenCode — `--agent opencode`. Если в проекте уже есть wiki, уберите `--init-wiki`. Чтобы предварительно посмотреть список изменений, добавьте `--dry-run`.

Команда выше ставит текущую версию из ветки `main`. Чтобы поставить стабильный релиз, клонируйте репозиторий на теге релиза и укажите канал `release`:

```bash
git clone --branch v0.2.0 https://github.com/mesilov/llm-wiki-skill.git
```

```bash
python3 llm-wiki-skill/scripts/install.py /path/to/project --init-wiki --channel release
```

## Проверка wiki

Запустите из проекта, куда установлен комплект.

```bash
bin/wiki/lint --dry-run
```

CLI проверяет локальные ссылки и структуру wiki и предупреждает, если нет обязательных страниц `knowledge/GLOSSARY.md` и `knowledge/log.md`. Для проверки формата источников используйте `bin/wiki/raw-lint` после установки зависимостей из `bin/wiki/requirements.txt`. За проверку содержания отвечает навык `wiki-lint`. [Формат источников](skills/wiki-query/references/raw.md) · [Глоссарий и журнал](skills/wiki-query/references/glossary.md) · [Правила работы с wiki](skills/wiki-query/references/contract.md)

## Обновление инструментов

```bash
bin/wiki/update --check
bin/wiki/update
```

Первая команда проверяет наличие обновления. Вторая предлагает его установить.

Updater берёт обновления из канала, выбранного при установке. Канал `main` следует за последним коммитом ветки `main`. Канал `release` следует за последним стабильным релизом на GitHub. Чтобы сменить канал, добавьте `--channel main` или `--channel release`. Новый канал сохраняется для следующих обновлений.

Updater меняет только навыки и `bin/wiki/`. Файлы в `raw/` и `knowledge/` не меняются. Если вы правили управляемые файлы вручную, updater остановится. С флагом `--force` он заменит их и сохранит прежние версии в `.wiki-kit-backups/`. Список изменений по версиям — в [CHANGELOG](CHANGELOG.md).

Лицензия [MIT](LICENSE). Для сторонних материалов действуют их лицензии.

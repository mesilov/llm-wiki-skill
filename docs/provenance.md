# Происхождение комплекта

Донор: `mesilov/pdlc-llm-wiki4sdlc-skill`, локальный checkout на commit
`5602547` (проверен 2026-11-11). Код и инструкции распространяются под MIT;
уведомление `Copyright (c) 2026 mesilov` сохранено в корне и каждом навыке.

Заимствованы и адаптированы:

- Markdown-парсер ссылок и поиск влияния из `bin/wiki/_core.py`;
- manifest, проверка путей, получение архива, планирование, backup и rollback
  из `_kit.py` и `_update.py`, установщик `scripts/install.py`;
- независимые тесты ссылок и updater;
- принципы источников, синтеза, неопределённости, границ чтения/записи;
- полный каталог `skills/wiki-query/references/utr-source/`;
- шаблоны `GLOSSARY.md` и `log.md`, правила глоссария и журнала
  из `references/glossary.md` и таблиц метастраниц навыков.

В этом наборе четыре навыка вместо восьми. Убраны PDLC, OpenSpec, forge doctor,
профиль конфигурации и CLI-проверки решений и глоссария, включая `lint --fix`.
Raw использует минимальный envelope вместо формата OKF донора. Updater получил
безопасное неинтерактивное подтверждение `--yes` и защиту локальных удалений.

SimpleEn-RU: `GregoryPletnev/SimpleEn-RU`, commit
`aefcd51664f549801758bd5530d9e0f6bba415fc`. Восемь исходных файлов проверяются
по [manifest](../skills/wiki-query/references/utr-source/manifest.json).
Исходный SKILL.md переименован в SKILL.source.md без изменения содержимого.
Сохранена [MIT-лицензия](../skills/wiki-query/references/utr-source/LICENSE)
с уведомлением `Copyright (c) 2026 AminBlg`.

Справочник содержит авторский пересказ стандарта. Полная нормативная сверка
этим проектом не проводилась; копирование не означает подтверждения всех
фактических утверждений исходника. Wiki-обвязка явно отделена от исходного текста.

При реализации raw-lint использована [официальная документация PyYAML](https://pyyaml.org/wiki/PyYAMLDocumentation)
о SafeLoader. Context7 в этой сессии был недоступен среди подключённых инструментов.

# Compatibility / Сумісність / Совместимость

**English.** Which players were tested with this toolkit and what worked. A row is added only from a first-hand result: your
[hardware test report](https://github.com/zanzipanzi/atj2157-player-toolkit/issues/new?template=hardware-report.yml) or the
maintainer's own test. Rows marked "documented elsewhere" come from other projects and have **not** been tested with these tools.

**Українською.** Які плеєри перевірено з цим набором і що спрацювало. Рядок додається лише за результатом з перших рук: вашим
[звітом про перевірку](https://github.com/zanzipanzi/atj2157-player-toolkit/issues/new?template=hardware-report.yml) або власною
перевіркою автора. Рядки «описано деінде» взято з інших проєктів, **з цими інструментами не перевірено**.

**По-русски.** Какие плееры проверены с этим набором и что сработало. Строка добавляется только по результату из первых рук:
вашему [отчёту о проверке](https://github.com/zanzipanzi/atj2157-player-toolkit/issues/new?template=hardware-report.yml) или
собственной проверке автора. Строки «описано в другом месте» взяты из других проектов, **с этими инструментами не проверены**.

Legend / Умовні позначки / Обозначения: ✅ works on a real player / працює на справжньому плеєрі / работает на настоящем плеере ·
⚠️ partly / частково / частично · ❌ does not work / не працює / не работает · ❔ not tested / не перевірено / не проверено

| Player / Плеєр / Плеер | Chip / Чип | Flash / Флешка | Firmware / Прошивка | Font / Шрифт (RU, UK) | Video / Відео / Видео | Flash read/write / Читання, запис / Чтение, запись | Source / Джерело / Источник |
|---|---|---|---|---|---|---|---|
| Generic "iPod nano" clone, 1.8" screen, microSD, no model name (USB `10d6:1101`) | ATJ2157 | GD25Q32, 4 MiB | `1.101.56` | ✅ both | ❔ converter passes the firmware's own parser (emulated), not tried on the player | ✅ read, guarded write of 4 sectors | maintainer |
| AGPTEK A02 | ATJ2157 | documented elsewhere | documented elsewhere | ❔ | ❔ | ❔ | [a02-os](https://github.com/TheWirelessPhoenix/a02-os) documents the chip and its ADFU flash procedure; not tested with these tools |

To add your player: open a **Hardware test report** and say which of the columns you tested.
Щоб додати свій плеєр: заповніть форму **Hardware test report** і вкажіть, які стовпці ви перевіряли.
Чтобы добавить свой плеер: заполните форму **Hardware test report** и укажите, какие столбцы вы проверяли.

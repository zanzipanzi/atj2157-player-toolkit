# Где взять всё нужное

В этом репозитории **нет прошивок, кода производителя и шрифтов**. Всё ниже - либо свободное ПО, которое вы ставите сами,
либо то, что вы берёте со **своего плеера**. Другие языки: [English](where-to-get.md), [Українська](where-to-get.uk.md).
Прочитайте [SAFETY.md](../SAFETY.md), прежде чем что-то записывать в плеер.

| Что нужно | Для чего | Откуда |
|---|---|---|
| Python 3.10+ | все `tools/` | https://www.python.org/downloads/ |
| `ffmpeg` | конвертер видео | https://ffmpeg.org/download.html (Windows: `winget install Gyan.FFmpeg`, Debian/Ubuntu: `apt install ffmpeg`) |
| `actions_dump` + `adfus.bin` | связь с чипом по USB | https://github.com/ilyakurdyukov/actions_flash (собираете сами, см. ниже) |
| `arm-none-eabi-gcc` | сборка `payload/` | `apt install gcc-arm-none-eabi` или https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads |
| Linux с USB | всё, что трогает чип | `actions_dump` - инструмент для Linux (libusb): https://libusb.info/ |
| ваш дамп прошивки | `lfi_tool.py`, правка шрифта | вы читаете его со **своего** плеера (ниже) |
| донорский шрифт | правка кириллицы и украинского | собрать свободный из GNU Unifont (рекомендуется) или другие варианты ниже |
| `MMM_VP.AL` | только необязательная проверка эмулятором | достаётся из **вашего** дампа прошивки (ниже) |

## 1. `actions_dump` и `adfus.bin`

```
git clone https://github.com/ilyakurdyukov/actions_flash
cd actions_flash && make                  # собирает actions_dump (нужен пакет разработчика libusb-1.0)
cd payload_arm && make NAME=adfus         # собирает adfus.bin для ATJ2157 (нужен arm-none-eabi-gcc)
```

`adfus.bin` собирается из открытых исходников, так что скачивать ничего не нужно. Для ATJ2157 его нужно загружать по адресу
`0x118000` (см. README проекта). Запускайте `actions_dump` из этого каталога: shell-скрипты из
[`payload/host/`](../payload/host) ожидают его в текущей папке.

## 2. Ваш собственный дамп прошивки

1. Переведите плеер в режим ADFU (аппаратная кнопка, см. [технические заметки, раздел 1](technical-notes.ru.md)) и проверьте чип
   командой `adfu_info`.
2. Соберите payload (`make -C payload`), скопируйте `payload/*.bin` и `payload/host/*.sh` в свой `actions_flash`
   (скрипты вызывают `./actions_dump` и загружают `spiread.bin` из текущего каталога), запустите `adfus` и прочитайте
   флешку дважды: сырой и расшифрованной. Скрипт только **читает** ([технические заметки, раздел 4](technical-notes.ru.md)):

   ```
   sudo ./actions_dump chip 2157 simple_switch 0x118000 adfus.bin
   SIZE=4194304 F68=0 OUT=dump_raw.bin   ./dump_spi.sh      # как лежит на флешке
   SIZE=4194304 F68=1 OUT=dump_plain.bin ./dump_spi.sh      # расшифрованная контроллером
   ```
3. Проверьте расшифрованный образ: `python tools/lfi_tool.py validate dump_plain.bin` должен показать `OK` для каждой суммы.
4. Сохраните оба дампа. Это ваша резервная копия и источник для отката. **Никогда не публикуйте их.**

## 3. Донорский шрифт (только для правки кириллицы и украинского)

Инструменты правки копируют кириллические глифы из файла-«донора» (65536 записей по 33 байта, раскладка `UNICODE.FON` от
Actions). Три способа его достать, от лучшего:

**а) Собрать свободный донор из GNU Unifont (рекомендуется: ничего проприетарного).**
Unifont - свободное ПО (SIL Open Font License 1.1 или GPL 2+ с исключением для встраивания шрифтов) и покрывает весь
кириллический блок, включая `Є І Ї Ґ`.

```
curl -LO https://ftp.gnu.org/gnu/unifont/unifont-18.0.01/unifont_all-18.0.01.hex.gz   # новые версии: https://ftp.gnu.org/gnu/unifont/
python tools/make_donor_from_unifont.py unifont_all-18.0.01.hex.gz donor.FON --preview preview.png
python tools/fnt_patch.py   NEW_M.FNT      donor.FON NEW_M_ru.FNT      # узкие русские буквы
python tools/fnt_add_ukr.py NEW_M_ru.FNT   donor.FON NEW_M_uk.FNT      # добавить Є І Ї Ґ
```

Буквы 8x16, чуть шире и круглее оригинального шрифта Actions; по умолчанию их делают пропорциональными (пустые столбцы
обрезаются). `--mono` оставляет фиксированный шаг 8 px. Картинка-просмотр показывает только кириллицу (пробелы и знаки
препинания берутся из шрифта самого плеера, поэтому слова в этом просмотре слиплись).

**б) Стандартный шрифт из SDK Actions.** `UNICODE.FON` из SDK Actions - тот же файл, что идёт в прошивке AGPTEK A02; мы
проверили, что оба файла побайтно идентичны (2 162 688 байт, SHA-256
`4ebc2bed57ac29ab145c11455d4a5ae67a4bce7aae07cfd14676b4ffbadb1c85`). Он есть в публичном стороннем репозитории с исходниками
SDK Actions:
https://github.com/malos17713/US212A_ATJ2127/tree/master/case/fwpkg/font (сам файл:
`https://raw.githubusercontent.com/malos17713/US212A_ATJ2127/master/case/fwpkg/font/UNICODE.FON`).
**Мы не размещаем и не поддерживаем этот репозиторий**; оценивать его правовой статус не нам, поэтому проверьте, что разрешено у
вас, или предпочтите вариант (а). Проверяйте скачанное командой `sha256sum UNICODE.FON`.

**в) Из прошивки другого плеера Actions.** Извлеките `UNICODE.FON` из дампа прошивки того плеера командой
`python tools/lfi_tool.py extract dump_plain.bin out/`. AGPTEK A02 (тоже ATJ2157) описан, вместе с инструментами, которые
скачивают его официальное обновление и проверяют по хешу, в https://github.com/TheWirelessPhoenix/a02-os (см. его
`docs/FLASH-INSTALL.md`).

## 4. `MMM_VP.AL` (необязательно)

Видеомодуль плеера нужен только `tools/mmm_vp_walker_emu.py` (и дополнительной проверке внутри `make_player_avi.py`). Возьмите его
из **своего** дампа и укажите инструменту:

```
python tools/lfi_tool.py extract dump_plain.bin out/
export MMM_VP_AL=out/MMM_VP.AL        # Windows PowerShell: $env:MMM_VP_AL = "out\MMM_VP.AL"
pip install -r requirements.txt       # ставит unicorn (эмулятор процессора) и pytest
python tools/make_player_avi.py фильм.mp4 для_плеера.avi
```

Без него конвертер всё равно работает и сообщает, что проверка разбором из прошивки пропущена.

## 5. Связанные проекты, о которых стоит знать

- [actions_flash](https://github.com/ilyakurdyukov/actions_flash): `actions_dump`, набор команд ADFU, `fwhelper` для образов LFI.
- [a02-os](https://github.com/TheWirelessPhoenix/a02-os) (MIT): открытая ОС-замена для AGPTEK A02 (ATJ2157) с описанными
  процедурами прошивки; полезно, если ваш плеер - A02.
- [Rockbox `atjboottool`](https://github.com/Rockbox/rockbox/tree/master/utils/atj2137/atjboottool): расшифровывает файлы
  обновления `UPGRADE.HEX` / `.FWU` плееров ATJ213x/ATJ2127.

Никогда не загружайте прошивки, дампы и шрифты, взятые с устройства, в этот репозиторий или в issue. Для описания находки
достаточно хешей, смещений и коротких фрагментов hex.

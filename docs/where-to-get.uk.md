# Де взяти все потрібне

У цьому репозиторії **немає прошивок, коду виробника й шрифтів**. Усе нижче - або вільне програмне забезпечення, яке ви
встановлюєте самі, або те, що ви берете зі **свого плеєра**. Інші мови: [English](where-to-get.md),
[Русский](where-to-get.ru.md). Прочитайте [SAFETY.md](../SAFETY.md), перш ніж щось записувати в плеєр.

| Що потрібно | Для чого | Звідки |
|---|---|---|
| Python 3.10+ | усі `tools/` | https://www.python.org/downloads/ |
| `ffmpeg` | конвертер відео | https://ffmpeg.org/download.html (Windows: `winget install Gyan.FFmpeg`, Debian/Ubuntu: `apt install ffmpeg`) |
| `actions_dump` + `adfus.bin` | зв'язок із чипом по USB | https://github.com/ilyakurdyukov/actions_flash (збираєте самі, див. нижче) |
| `arm-none-eabi-gcc` | збирання `payload/` | `apt install gcc-arm-none-eabi` або https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads |
| Linux із USB | усе, що торкається чипа | `actions_dump` - інструмент для Linux (libusb): https://libusb.info/ |
| ваш дамп прошивки | `lfi_tool.py`, правка шрифту | ви читаєте його зі **свого** плеєра (нижче) |
| донорський шрифт | правка кирилиці й української | зібрати вільний із GNU Unifont (рекомендовано) або інші варіанти нижче |
| `MMM_VP.AL` | лише необов'язкова перевірка емулятором | дістається з **вашого** дампа прошивки (нижче) |

## 1. `actions_dump` і `adfus.bin`

```
git clone https://github.com/ilyakurdyukov/actions_flash
cd actions_flash && make                  # збирає actions_dump (потрібен пакет розробника libusb-1.0)
cd payload_arm && make NAME=adfus         # збирає adfus.bin для ATJ2157 (потрібен arm-none-eabi-gcc)
```

`adfus.bin` збирається з відкритих джерел, тож завантажувати нічого не треба. Для ATJ2157 його слід завантажувати за адресою
`0x118000` (див. README проєкту). Запускайте `actions_dump` з цього каталогу: shell-скрипти з
[`payload/host/`](../payload/host) очікують його в поточній теці.

## 2. Ваш власний дамп прошивки

1. Переведіть плеєр у режим ADFU (апаратна кнопка, див. [технічні нотатки, розділ 1](technical-notes.uk.md)) і перевірте чип
   командою `adfu_info`.
2. Зберіть payload (`make -C payload`), скопіюйте `payload/*.bin` і `payload/host/*.sh` у свій `actions_flash`
   (скрипти викликають `./actions_dump` і завантажують `spiread.bin` з поточного каталогу), запустіть `adfus` і прочитайте
   флешку двічі: сирою й розшифрованою. Скрипт лише **читає** ([технічні нотатки, розділ 4](technical-notes.uk.md)):

   ```
   sudo ./actions_dump chip 2157 simple_switch 0x118000 adfus.bin
   SIZE=4194304 F68=0 OUT=dump_raw.bin   ./dump_spi.sh      # як лежить на флешці
   SIZE=4194304 F68=1 OUT=dump_plain.bin ./dump_spi.sh      # розшифрований контролером
   ```
3. Перевірте розшифрований образ: `python tools/lfi_tool.py validate dump_plain.bin` має показати `OK` для кожної суми.
4. Збережіть обидва дампи. Це ваша резервна копія й джерело для відкату. **Ніколи їх не публікуйте.**

## 3. Донорський шрифт (лише для правки кирилиці й української)

Інструменти правки копіюють кириличні гліфи з файла-«донора» (65536 записів по 33 байти, розкладка `UNICODE.FON` від
Actions). Три способи його дістати, від найкращого:

**а) Зібрати вільний донор із GNU Unifont (рекомендовано: нічого пропрієтарного).**
Unifont - вільне ПЗ (SIL Open Font License 1.1 або GPL 2+ з винятком для вбудовування шрифтів) і покриває весь кириличний блок,
зокрема `Є І Ї Ґ`.

```
curl -LO https://ftp.gnu.org/gnu/unifont/unifont-18.0.01/unifont_all-18.0.01.hex.gz   # новіші версії: https://ftp.gnu.org/gnu/unifont/
python tools/make_donor_from_unifont.py unifont_all-18.0.01.hex.gz donor.FON --preview preview.png
python tools/fnt_patch.py   NEW_M.FNT      donor.FON NEW_M_ru.FNT      # вузькі російські літери
python tools/fnt_add_ukr.py NEW_M_ru.FNT   donor.FON NEW_M_uk.FNT      # додати Є І Ї Ґ
```

Літери 8x16, трохи ширші й округліші за оригінальний шрифт Actions; за замовчуванням їх робимо пропорційними (порожні стовпці
обрізаємо). `--mono` лишає фіксований крок 8 px. Картинка-перегляд показує лише кирилицю (пробіли й розділові знаки беруться зі
шрифту самого плеєра, тому слова в цьому перегляді склеєні).

**б) Стандартний шрифт з SDK Actions.** `UNICODE.FON` з SDK Actions - це той самий файл, що йде в прошивці AGPTEK A02; ми
перевірили, що обидва файли побайтно ідентичні (2 162 688 байт, SHA-256
`4ebc2bed57ac29ab145c11455d4a5ae67a4bce7aae07cfd14676b4ffbadb1c85`). Він є в публічному сторонньому репозиторії з вихідними
кодами SDK Actions:
https://github.com/malos17713/US212A_ATJ2127/tree/master/case/fwpkg/font (сам файл:
`https://raw.githubusercontent.com/malos17713/US212A_ATJ2127/master/case/fwpkg/font/UNICODE.FON`).
**Ми не розміщуємо й не підтримуємо цей репозиторій**; оцінювати його правовий статус не нам, тож перевірте, що дозволено у вас,
або віддайте перевагу варіантові (а). Перевіряйте завантаження командою `sha256sum UNICODE.FON`.

**в) З прошивки іншого плеєра Actions.** Витягніть `UNICODE.FON` із дампа прошивки того плеєра командою
`python tools/lfi_tool.py extract dump_plain.bin out/`. AGPTEK A02 (теж ATJ2157) описано, разом з інструментами, що
завантажують його офіційне оновлення й перевіряють за хешем, у https://github.com/TheWirelessPhoenix/a02-os (див. його
`docs/FLASH-INSTALL.md`).

## 4. `MMM_VP.AL` (необов'язково)

Відеомодуль плеєра потрібен лише `tools/mmm_vp_walker_emu.py` (і додатковій перевірці всередині `make_player_avi.py`). Візьміть його
зі **свого** дампа й вкажіть інструментові:

```
python tools/lfi_tool.py extract dump_plain.bin out/
export MMM_VP_AL=out/MMM_VP.AL        # Windows PowerShell: $env:MMM_VP_AL = "out\MMM_VP.AL"
pip install -r requirements.txt       # ставить unicorn (емулятор процесора) і pytest
python tools/make_player_avi.py film.mp4 for_player.avi
```

Без нього конвертер усе одно працює й повідомляє, що перевірку розбором із прошивки пропущено.

## 5. Пов'язані проєкти, про які варто знати

- [actions_flash](https://github.com/ilyakurdyukov/actions_flash): `actions_dump`, набір команд ADFU, `fwhelper` для образів LFI.
- [a02-os](https://github.com/TheWirelessPhoenix/a02-os) (MIT): відкрита ОС-заміна для AGPTEK A02 (ATJ2157) з описаними
  процедурами прошивання; корисно, якщо ваш плеєр - A02.
- [Rockbox `atjboottool`](https://github.com/Rockbox/rockbox/tree/master/utils/atj2137/atjboottool): розшифровує файли
  оновлення `UPGRADE.HEX` / `.FWU` для плеєрів ATJ213x/ATJ2127.

Ніколи не завантажуйте прошивки, дампи чи шрифти, взяті з пристрою, у цей репозиторій чи в issue. Для опису знахідки
достатньо хешів, зміщень і коротких фрагментів hex.

# Safety / Безопасность / Безпека

## English

This repository contains tools that **write to the firmware flash of a media player**. A wrong write can leave the player
unusable. Use it on a device you own, and only after you have:

1. **Found the hardware key that enters ADFU service mode and confirmed it works** (on the tested unit: hold the centre
   button while plugging USB with the slider OFF). Without a way back in, a bad write may be unrecoverable.
2. **Made and verified a full backup of the flash** (raw and descrambled) and stored it away from the repository.
3. **Checked the chip** with `adfu_info`. Loading code meant for another chip can hang the unit.
4. **Tested the write path on an erased, unused sector** before touching real data. A write to a protected area is silently
   ignored by the chip, so a test that merely "reads back the same value" proves nothing; use an independent signal such
   as the busy-poll counters.
5. Used the **dry run** first and typed the confirmation for every sector.

Things to know:

- The rollback path writes the original raw bytes back. It has been proven only on a free sector, **never on the real
  sectors** of the tested unit.
- A program that hangs in service mode can leave the player dead for days until the battery runs flat.
- The sector whitelist and the file offsets in this repository belong to **one firmware version** (`1.101.56`). Other
  firmware moves things around.
- Do not publish firmware dumps: they are the vendor's copyrighted code and contain identifiers of your unit. The
  `.gitignore` excludes the usual file types; please keep it that way. No warranty, see [LICENSE](LICENSE).

## Русский

В репозитории есть инструменты, которые **записывают в прошивочную флешку плеера**. Ошибка может сделать плеер
неработоспособным. Применяйте только к своему устройству и только после того, как вы:

1. **Нашли аппаратную кнопку входа в сервисный режим ADFU и убедились, что она работает** (на проверенном экземпляре:
   зажать центральную кнопку и подключить USB при выключателе в положении OFF). Без пути назад неудачная запись может
   оказаться необратимой.
2. **Сделали и проверили полную копию флешки** (сырую и расшифрованную) и храните её отдельно от репозитория.
3. **Проверили чип** командой `adfu_info`. Код для другого чипа может «повесить» устройство.
4. **Проверили запись на стёртом, неиспользуемом секторе**, прежде чем трогать настоящие данные. Запись в защищённую
   область чип молча игнорирует, поэтому проверка «прочитали то же самое» ничего не доказывает; нужен независимый
   признак, например счётчики ожидания готовности.
5. Сначала сделали **сухой прогон** и вводили подтверждение для каждого сектора.

Что важно знать:

- Откат записывает исходные сырые байты обратно. Проверен только на свободном секторе, **на настоящих секторах не
  запускался ни разу**.
- Программа, зависшая в сервисном режиме, может оставить плеер «мёртвым» на дни, пока не разрядится батарея.
- Белый список секторов и смещения файлов относятся к **одной версии прошивки** (`1.101.56`). В других версиях всё
  лежит иначе.
- Не публикуйте дампы прошивки: это защищённый авторским правом код производителя, в нём есть идентификаторы вашего
  экземпляра. `.gitignore` исключает обычные типы файлов, не убирайте эти правила. Без гарантий, см. [LICENSE](LICENSE).

## Українська

У репозиторії є інструменти, які **записують у прошивкову флешку плеєра**. Помилка може зробити плеєр непрацездатним.
Застосовуйте лише до власного пристрою й лише після того, як ви:

1. **Знайшли апаратну кнопку входу в сервісний режим ADFU і переконалися, що вона працює** (на перевіреному екземплярі:
   затиснути центральну кнопку й підключити USB при вимикачі в положенні OFF). Без шляху назад невдалий запис може
   виявитися незворотним.
2. **Зробили й перевірили повну копію флешки** (сиру та розшифровану) і зберігаєте її окремо від репозиторію.
3. **Перевірили чип** командою `adfu_info`. Код для іншого чипа може «повісити» пристрій.
4. **Перевірили запис на стертому, невикористаному секторі**, перш ніж торкатися справжніх даних. Запис в захищену
   область чип мовчки ігнорує, тому перевірка «прочитали те саме» нічого не доводить; потрібна незалежна ознака,
   наприклад лічильники очікування готовності.
5. Спершу зробили **сухий прогін** і вводили підтвердження для кожного сектора.

Що важливо знати:

- Відкат записує вихідні сирі байти назад. Перевірений лише на вільному секторі, **на справжніх секторах не запускався
  жодного разу**.
- Програма, що зависла в сервісному режимі, може залишити плеєр «мертвим» на дні, поки не розрядиться батарея.
- Білий список секторів і зміщення файлів стосуються **однієї версії прошивки** (`1.101.56`). В інших версіях усе
  лежить інакше.
- Не публікуйте дампи прошивки: це захищений авторським правом код виробника, у ньому є ідентифікатори вашого
  екземпляра. `.gitignore` виключає звичайні типи файлів, не прибирайте ці правила. Без гарантій, див. [LICENSE](LICENSE).

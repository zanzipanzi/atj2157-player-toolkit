# Contributing

Thanks for looking at this. The most valuable contribution is a **report from a real player**, because most of what is
here was verified on a single unit.

## Reports from real players (most wanted)

Open an issue with the **Hardware test report** form: what you tried (video AVI/AMV, font patch, flash read/write), the
player and chip (`adfu_info` answer), the firmware version string, and the result. Failures are as useful as successes.
Issues in English, Russian or Ukrainian are all fine.

## Hard rules

- **Never attach or commit firmware, ROM or flash dumps, unpacked firmware files, donor fonts, photos of a device or
  anything that carries a serial number or user data.** They are the vendor's copyrighted code and identify your unit.
  The `.gitignore` blocks the usual file types; do not work around it. To describe a finding, give hashes, offsets and
  short hex excerpts.
- Read [SAFETY.md](SAFETY.md) before running or proposing anything that writes to flash. Do not widen the address
  whitelist in `payload/spiwrite.c` without evidence from a dump of the same firmware.
- Mark anything you did not test on hardware as **(unverified)** in the docs.

## Code changes

```
pip install -r requirements.txt
python -m pytest tools/tests -q
```

Python 3.10+, small functions, no new dependencies without a reason. CI runs the tests on Python 3.10-3.13 and builds the
chip payloads. By contributing you agree that your code is released under the MIT license and your text and charts
under CC BY 4.0.

## Conduct and security

See the [Code of Conduct](CODE_OF_CONDUCT.md). Security-relevant problems (for example a way around the whitelist or the
dry run, or a leaked identifier) should go through the private form described in [SECURITY.md](SECURITY.md).

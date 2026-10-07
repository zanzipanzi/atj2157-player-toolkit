# Security policy

This repository contains tools that can **write to the firmware flash of a media player**, and documentation of how that
flash is protected and scrambled. It does not contain any vendor code.

## What to report privately

- a way to bypass the address whitelist, the dry run or the confirmation in the write tools;
- a bug that could write outside the intended sector, or leave the protection bits changed;
- firmware, dumps, serial numbers or other identifiers that ended up in the repository or its history;
- supply-chain problems in the CI workflow or dependencies.

Please use **Security -> Report a vulnerability** on GitHub (private vulnerability reporting is enabled) instead of a
public issue. There is no bounty. Only the latest `main` is supported.

Ordinary bugs and hardware results belong in public issues.

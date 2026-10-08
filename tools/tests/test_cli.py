"""Every tool answers --help, and every console command in pyproject.toml points at a real callable."""
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
ROOT = TOOLS.parent
SCRIPTS = sorted(p for p in TOOLS.glob('*.py'))


def needs_unicorn(script: Path) -> bool:
    return script.name == 'mmm_vp_walker_emu.py'


@pytest.mark.parametrize('script', SCRIPTS, ids=lambda p: p.name)
def test_help_exits_zero(script):
    if needs_unicorn(script):
        pytest.importorskip('unicorn')
    done = subprocess.run([sys.executable, str(script), '--help'], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip(), 'help text is empty'


def console_scripts():
    tomllib = pytest.importorskip('tomllib')   # Python 3.11+
    data = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    return data['project']['scripts']


def test_every_script_has_a_command():
    wired = {target.split(':')[0] for target in console_scripts().values()}
    assert wired == {p.stem for p in SCRIPTS}


@pytest.mark.parametrize('name', ['atj2157-lfi', 'atj2157-lfi-replace', 'atj2157-fnt-patch', 'atj2157-fnt-add-ukr',
                                  'atj2157-font-transplant', 'atj2157-donor-from-unifont', 'atj2157-make-avi',
                                  'atj2157-vp-check'])
def test_entry_point_resolves(name):
    module, _, attr = console_scripts()[name].partition(':')
    if module == 'mmm_vp_walker_emu':
        pytest.importorskip('unicorn')
    assert callable(getattr(importlib.import_module(module), attr))

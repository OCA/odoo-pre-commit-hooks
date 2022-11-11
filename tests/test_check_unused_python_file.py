import os
from pathlib import Path
from typing import List

from oca_pre_commit_hooks.check_unused_python_file import main

FILE_NAMES = ["res_partner", "project_task", "helpdesk_ticket"]


def _gen_filepaths(filenames: List[str], basedir) -> List[str]:
    return [f"{os.path.join(basedir, filename)}.py" for filename in filenames]


def test_all_used_files(tmpdir):
    filepaths = _gen_filepaths(FILE_NAMES, tmpdir)
    init_file = os.path.join(tmpdir, "__init__.py")
    with open(init_file, "w", encoding="utf-8") as init_fd:
        init_fd.writelines([f"from . import {filename}\n" for filename in FILE_NAMES])

    for filepath in filepaths:
        Path(filepath).touch()

    assert main(filepaths) == 0

    Path(init_file).unlink()
    with open(init_file, "w", encoding="utf-8") as init_fd:
        init_fd.write(f"from . import {','.join(FILE_NAMES)}")

    assert main(filepaths) == 0


def test_all_unused_files(tmpdir):
    filepaths = _gen_filepaths(FILE_NAMES, tmpdir)
    init_file = os.path.join(tmpdir, "__init__.py")

    Path(init_file).touch()
    for filepath in filepaths:
        Path(filepath).touch()

    assert main(filepaths) == -1


def test_complex_init(tmpdir):
    filepaths = _gen_filepaths(FILE_NAMES, tmpdir)
    init_file = os.path.join(tmpdir, "__init__.py")
    with open(init_file, "w", encoding="utf-8") as init_fd:
        init_fd.writelines(
            ["def hello(cr):\n", "\treturn cr.commit()\n"] + [f"from . import {filename}\n" for filename in FILE_NAMES]
        )

    for filepath in filepaths:
        Path(filepath).touch()

    assert main(filepaths) == 0

    extra_file = os.path.join(tmpdir, "extrafile.py")
    Path(extra_file).touch()
    filepaths.append(extra_file)

    assert main(filepaths) == -1

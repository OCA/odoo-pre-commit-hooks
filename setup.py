#!/usr/bin/env python3

import re
from glob import glob
from os.path import basename, dirname, join, splitext

from setuptools import find_packages, setup

try:
    from pbr import git
except ImportError:
    git = None


def generate_changelog():
    fname = "ChangeLog"
    if not git:
        changelog_str = '# ChangeLog was not generated. You need to install "pbr"'
        with open(fname, "w", encoding="UTF-8") as fchg:
            fchg.write(changelog_str)
        return changelog_str
    # pylint: disable=protected-access
    changelog = git._iter_log_oneline()
    changelog = git._iter_changelog(changelog)
    git.write_git_changelog(changelog=changelog)
    # git.generate_authors()
    return read(fname)


def generate_dependencies():
    return read("requirements.txt").splitlines()


def read(*names, **kwargs):
    with open(join(dirname(__file__), *names), encoding=kwargs.get("encoding", "utf8")) as file_obj:
        return file_obj.read()


def generage_long_description():
    long_description = "{}\n{}".format(
        # re.compile(".*\(start-badges\).*^.*\(end-badges\)", re.M | re.S).sub("", read("README.md")),
        read("README.md"),
        re.sub(":[a-z]+:`~?(.*?)`", r"``\1``", generate_changelog()),
    )
    return long_description


setup(
    name="oca-odoo-pre-commit-hooks",
    version="0.0.28",
    license="LGPL-3.0-or-later",
    description="odoo-pre-commit-hooks to use in pre-commit-config.yml files",
    long_description=generage_long_description(),
    long_description_content_type="text/markdown",
    author="Odoo Community Association (OCA)",
    author_email="support@odoo-community.org",
    url="https://github.com/OCA/odoo-pre-commit-hooks",
    packages=find_packages("src"),
    package_dir={"": "src"},
    data_files=[("requirements", ["requirements.txt"])],
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Utilities",
    ],
    project_urls={
        "Issue Tracker": "https://github.com/OCA/odoo-pre-commit-hooks/issues",
    },
    keywords=[
        "pre-commit",
        "OCA",
        "Odoo Community Association",
        "pre-commit-hook",
    ],
    python_requires=">=3.7",
    install_requires=generate_dependencies(),
    extras_require={},
    entry_points={
        "console_scripts": [
            "oca-checks-odoo-module = oca_pre_commit_hooks.cli:main",
            "oca-checks-po = oca_pre_commit_hooks.cli_po:main",
        ]
    },
)

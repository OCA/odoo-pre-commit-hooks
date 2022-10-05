#!/usr/bin/env python
from __future__ import absolute_import, print_function

import io
import re
from glob import glob
from os.path import basename, dirname, join, splitext

from setuptools import find_packages, setup


def generate_dependencies():
    return read("requirements.txt").splitlines()


def read(*names, **kwargs):
    with io.open(join(dirname(__file__), *names), encoding=kwargs.get("encoding", "utf8")) as fh:
        return fh.read()


setup(
    name="odoo-pre-commit-hooks",
    version="0.0.1",
    license="LGPL-3.0-or-later",
    description="odoo-pre-commit-hooks to use in pre-commit-config.yml files",
    long_description="{}".format(
        re.compile("^.. start-badges.*^.. end-badges", re.M | re.S).sub("", read("README.rst")),
    ),
    author="Odoo Community Association (OCA)",
    author_email="support@odoo-community.org",
    url="https://github.com/OCA/odoo-pre-commit-hooks",
    packages=find_packages("src"),
    package_dir={"": "src"},
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
        "Programming Language :: Python :: 3.6",
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
        "oca",
        "Odoo Community Association",
    ],
    python_requires=">=3.5",
    install_requires=generate_dependencies(),
    extras_require={},
    entry_points={
        "console_scripts": [
            "odoo-missing-readme = checks_odoo_module:main_missing_readme",
            "odoo-rst-syntax = checks_rst:main_rst_syntax_error",
        ]
    },
)

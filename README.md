[![Pre-commit Status](https://github.com/OCA/odoo-pre-commit-hooks/actions/workflows/pre-commit.yml/badge.svg?branch=main)](https://github.com/OCA/odoo-pre-commit-hooks/actions/workflows/pre-commit.yml?query=branch%3Amain)
[![Build Status](https://github.com/OCA/odoo-pre-commit-hooks/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/OCA/odoo-pre-commit-hooks/actions/workflows/test.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/OCA/odoo-pre-commit-hooks/branch/main/graph/badge.svg)](https://codecov.io/gh/OCA/odoo-pre-commit-hooks)
[![version](https://img.shields.io/pypi/v/oca-odoo-pre-commit-hooks.svg)](https://pypi.org/project/oca-odoo-pre-commit-hooks)
[![wheel](https://img.shields.io/pypi/wheel/pre-commit-vauxoo.svg)](https://pypi.org/project/pre-commit-vauxoo)
[![supported-versions](https://img.shields.io/pypi/pyversions/pre-commit-vauxoo.svg)](https://pypi.org/project/pre-commit-vauxoo)
[![commits-since](https://img.shields.io/github/commits-since/Vauxoo/pre-commit-vauxoo/v0.0.1.svg)](https://github.com/Vauxoo/pre-commit-vauxoo/compare/v0.0.1...main)


# odoo-pre-commit-hooks

OCA's custom pre-commit hooks for Odoo modules


# Installation

You don't need to install it directly only configure your ".pre-commit-config.yaml" file

Even you can install using github directly

    pip install -U git+https://github.com/OCA/odoo-pre-commit-hooks.git@main


# Usage pre-commit-config.yaml

Add to your ".pre-commit-config.yaml" configuration file the following input


```yaml

    - repo: https://github.com/OCA/odoo-pre-commit-hooks
        rev: main  # Change to last version or git sha
        hooks:
        - id: HOOK-NAME

```

# Usage using directly the entry points

If you install directly the package from github you can use the entry points:

    * HOOK-APP (TODO ADD ALL HOOKS HERE)


## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to Odoo Community Association (OCA)
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

----
OCA, or the [Odoo Community Association](http://odoo-community.org/), is a nonprofit
organization whose mission is to support the collaborative development of Odoo features
and promote its widespread use.

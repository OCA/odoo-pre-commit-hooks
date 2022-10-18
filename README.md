[//]: # (start-badges)

[![Build Status](https://github.com/OCA/odoo-pre-commit-hooks/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/OCA/odoo-pre-commit-hooks/actions/workflows/test.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/OCA/odoo-pre-commit-hooks/branch/main/graph/badge.svg)](https://codecov.io/gh/OCA/odoo-pre-commit-hooks)
[![version](https://img.shields.io/pypi/v/oca-odoo-pre-commit-hooks.svg)](https://pypi.org/project/oca-odoo-pre-commit-hooks)
[![wheel](https://img.shields.io/pypi/wheel/oca-odoo-pre-commit-hooks.svg)](https://pypi.org/project/oca-odoo-pre-commit-hooks)
[![supported-versions](https://img.shields.io/pypi/pyversions/oca-odoo-pre-commit-hooks.svg)](https://pypi.org/project/oca-odoo-pre-commit-hooks)
[![commits-since](https://img.shields.io/github/commits-since/OCA/odoo-pre-commit-hooks/v0.0.5.svg)](https://github.com/OCA/odoo-pre-commit-hooks/compare/v0.0.5...main)
[![code-style-black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[//]: # (end-badges)

# odoo-pre-commit-hooks

OCA's custom pre-commit hooks for Odoo modules


# Installation

You don't need to install it directly only configure your ".pre-commit-config.yaml" file

You even can install it directly:
 - Installing from pypi:
   - pip install -U odoo-pre-commit-hooks
 - Installing from github:
   - pip install --force-reinstall -U git+https://github.com/OCA/odoo-pre-commit-hooks.git@main


# Usage pre-commit-config.yaml

Add to your ".pre-commit-config.yaml" configuration file the following input


```yaml
    - repo: https://github.com/OCA/odoo-pre-commit-hooks
        rev: v0.0.5
        hooks:
        - id: oca-checks-odoo-module
```

# Usage using directly the entry points

If you install directly the package use the entry point:

    oca-checks-odoo-module --help


[//]: # (start-checks)
# Checks

* Check manifest_syntax_error
        Check if the manifest file has syntax error

* Check missing_readme
        Check if a README file is missing

* Check csv_duplicate_record_id
        duplicate CSV "id" AKA xmlid but for CSV files

* Check csv_syntax_error
        Check syntax error for CSV files declared in the manifest

* Check po_requires_module
        Translation entry requires comment '#. module: MODULE'

* Check po_python_parse_printf
        Check if 'msgid' is using 'str' variables like '%s'
        So translation 'msgstr' must be the same number of variables too

* Check po_python_parse_format
        Check if 'msgid' is using 'str' variables like '{}'
        So translation 'msgstr' must be the same number of variables too

* Check po_duplicate_message_definition (message-id)
        in all entries of PO files

        We are not using `check_for_duplicates` parameter of polib.pofile method
            e.g. polib.pofile(..., check_for_duplicates=True)
        Because the output is:
            raise ValueError('Entry "%s" already exists' % entry.msgid)
        It doesn't show the number of lines duplicated
        and it shows the entire string of the message_id without truncating it
        or replacing newlines

* Check po_syntax_error
        Check syntax of PO files from i18n* folders

* Check xml_redundant_module_name

        If the module is called "module_a" and the xmlid is
        <record id="module_a.xmlid_name1" ...

        The "module_a." is redundant it could be replaced to only
        <record id="xmlid_name1" ...

* Check xml_dangerous_filter_wo_user
        Check dangerous filter without a user assigned.

* Check xml_create_user_wo_reset_password
        records of user without context="{'no_reset_password': True}"
        This context avoid send email and mail log warning

* Check xml_view_dangerous_replace_low_priority in ir.ui.view

            <field name="priority" eval="10"/>
            ...
                <field name="name" position="replace"/>

* Check xml_deprecated_tree_attribute
          The tree-view declaration is using a deprecated attribute.

* Check xml_dangerous_qweb_replace_low_priority
        Dangerous qweb view defined with low priority

* Check xml_deprecated_data_node
        Deprecated <data> node inside <odoo> xml node

* Check xml_deprecated_openerp_xml_node
        deprecated <openerp> xml node

* Check xml_deprecated_qweb_directive
        for use of deprecated QWeb directives t-*-options

* Check xml_not_valid_char_link
        The resource in in src/href contains a not valid character.

* Check xml_duplicate_record_id

        If a module has duplicated record_id AKA xml_ids
        file1.xml
            <record id="xmlid_name1"
        file2.xml
            <record id="xmlid_name1"

* Check xml_duplicate_fields in all record nodes
            <record id="xmlid_name1"...
                <field name="field_name1"...
                <field name="field_name1"...

* Check xml_syntax_error
        Check syntax of XML files declared in the Odoo manifest

[//]: # (end-checks)


## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to Odoo Community Association (OCA)
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

----
OCA, or the [Odoo Community Association](http://odoo-community.org/), is a nonprofit
organization whose mission is to support the collaborative development of Odoo features
and promote its widespread use.

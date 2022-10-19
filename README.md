[//]: # (start-badges)

[![Build Status](https://github.com/OCA/odoo-pre-commit-hooks/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/OCA/odoo-pre-commit-hooks/actions/workflows/test.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/OCA/odoo-pre-commit-hooks/branch/main/graph/badge.svg)](https://codecov.io/gh/OCA/odoo-pre-commit-hooks)
[![version](https://img.shields.io/pypi/v/oca-odoo-pre-commit-hooks.svg)](https://pypi.org/project/oca-odoo-pre-commit-hooks)
[![wheel](https://img.shields.io/pypi/wheel/oca-odoo-pre-commit-hooks.svg)](https://pypi.org/project/oca-odoo-pre-commit-hooks)
[![supported-versions](https://img.shields.io/pypi/pyversions/oca-odoo-pre-commit-hooks.svg)](https://pypi.org/project/oca-odoo-pre-commit-hooks)
[![commits-since](https://img.shields.io/github/commits-since/OCA/odoo-pre-commit-hooks/v0.0.9.svg)](https://github.com/OCA/odoo-pre-commit-hooks/compare/v0.0.9...main)
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
        rev: v0.0.9
        hooks:
        - id: oca-checks-odoo-module
```

# Usage directly the entry points

If you install directly the package use the entry point:

    oca-checks-odoo-module --help


[//]: # (start-checks)

# Checks

* Check manifest-syntax-error
        Check if the manifest file has syntax error

* Check missing-readme
        Check if a README file is missing

* Check csv-duplicate-record-id
        duplicate CSV "id" AKA xmlid but for CSV files

* Check csv-syntax-error
        Check syntax error for CSV files declared in the manifest

* Check po-requires-module
        Translation entry requires comment '#. module: MODULE'

* Check po-python-parse-printf
        Check if 'msgid' is using 'str' variables like '%s'
        So translation 'msgstr' must be the same number of variables too

* Check po-python-parse-format
        Check if 'msgid' is using 'str' variables like '{}'
        So translation 'msgstr' must be the same number of variables too

* Check po-duplicate-message-definition (message-id)
        in all entries of PO files

        We are not using `check_for_duplicates` parameter of polib.pofile method
            e.g. polib.pofile(..., check_for_duplicates=True)
        Because the output is:
            raise ValueError('Entry "%s" already exists' % entry.msgid)
        It doesn't show the number of lines duplicated
        and it shows the entire string of the message_id without truncating it
        or replacing newlines

* Check po-syntax-error
        Check syntax of PO files from i18n* folders

* Check xml-redundant-module-name

        If the module is called "module_a" and the xmlid is
        <record id="module_a.xmlid_name1" ...

        The "module_a." is redundant it could be replaced to only
        <record id="xmlid_name1" ...

* Check xml-dangerous-filter-wo-user
        Check dangerous filter without a user assigned.

* Check xml-create-user-wo-reset-password
        records of user without context="{'no_reset_password': True}"
        This context avoid send email and mail log warning

* Check xml-view-dangerous-replace-low-priority in ir.ui.view

            <field name="priority" eval="10"/>
            ...
                <field name="name" position="replace"/>

* Check xml-deprecated-tree-attribute
          The tree-view declaration is using a deprecated attribute.

* Check xml-dangerous-qweb-replace-low-priority
        Dangerous qweb view defined with low priority

* Check xml-deprecated-data-node
        Deprecated <data> node inside <odoo> xml node

* Check xml-deprecated-openerp-xml-node
        deprecated <openerp> xml node

* Check xml-deprecated-qweb-directive
        for use of deprecated QWeb directives t-*-options

* Check xml-not-valid-char-link
        The resource in in src/href contains a not valid character.

* Check xml-duplicate-record-id

        If a module has duplicated record_id AKA xml_ids
        file1.xml
            <record id="xmlid_name1"
        file2.xml
            <record id="xmlid_name1"

* Check xml-duplicate-fields in all record nodes
            <record id="xmlid_name1"...
                <field name="field_name1"...
                <field name="field_name1"...

* Check xml-syntax-error
        Check syntax of XML files declared in the Odoo manifest


[//]: # (end-checks)


[//]: # (start-help)

# Help
```bash
usage: oca-checks-odoo-module [-h] [--no-verbose] [--no-exit]
                              [--disable DISABLE] [--enable ENABLE]
                              [files_or_modules [files_or_modules ...]]

positional arguments:
  files_or_modules      Odoo __manifest__.py paths or Odoo module paths.

optional arguments:
  -h, --help            show this help message and exit
  --no-verbose          If enabled so disable verbose mode.
  --no-exit             If enabled so it will not call exit.
  --disable DISABLE, -d DISABLE
                        Disable the checker with the given 'check-name',
                        separated by commas.
  --enable ENABLE, -e ENABLE
                        Enable the checker with the given 'check-name',
                        separated by commas. Default: All checks are enabled
                        by default

```

[//]: # (end-help)


[//]: # (start-example)

# Examples


 * csv-duplicate-record-id

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/ir.model.access.csv#L5 Duplicate CSV record id "data/access_account_account_type" in test_repo/broken_module/ir.model.access.csv:6

 * missing-readme

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/README.rst#L1 missed file. Template here: https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst

 * po-python-parse-printf

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L47 Translation string couldn't be parsed correctly using str%variables TypeError('not all arguments converted during string formatting')
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L83 Translation string couldn't be parsed correctly using str%variables TypeError('%d format: a number is required, not str')

 * po-python-parse-format

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L53 Translation string couldn't be parsed correctly using str.format IndexError('Replacement index 1 out of range for positional args tuple')
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L59 Translation string couldn't be parsed correctly using str.format IndexError('Replacement index 1 out of range for positional args tuple')
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L65 Translation string couldn't be parsed correctly using str.format KeyError('variable2')
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L71 Translation string couldn't be parsed correctly using str.format KeyError('variable2')

 * po-duplicate-message-definition

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L17 Duplicate PO message definition "Branch" in lines 23, 29
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L35 Duplicate PO message definition "Message id toooooooooooooooooooooooooooo..." in lines 41
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/es.po#L65 Duplicate PO message definition "One variable {variable1}" in lines 71

 * po-requires-module

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/i18n/broken_module.pot#L14 Translation entry requires comment '#. module: MODULE'

 * xml-dangerous-qweb-replace-low-priority

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/template1.xml#L3 Dangerous use of "replace" from view with priority 0 < 99
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/template1.xml#L3 Dangerous use of "replace" from view with priority 0 < 99
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/template1.xml#L17 Dangerous use of "replace" from view with priority 0 < 99

 * xml-deprecated-data-node

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view.xml#L2 Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` instead of `<odoo><data noupdate="1">`
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L2 Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` instead of `<odoo><data noupdate="1">`
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo.xml#L2 Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` instead of `<odoo><data noupdate="1">`
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L2 Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` instead of `<odoo><data noupdate="1">`
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/skip_xml_check.xml#L3 Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` instead of `<odoo><data noupdate="1">`
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/skip_xml_check_3.xml#L4 Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` instead of `<odoo><data noupdate="1">`
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/demo/duplicated_id_demo.xml#L2 Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` instead of `<odoo><data noupdate="1">`

 * xml-deprecated-openerp-xml-node

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view.xml#L2 Deprecated <openerp> xml node
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L2 Deprecated <openerp> xml node
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/skip_xml_check_2.xml#L2 Deprecated <openerp> xml node

 * xml-redundant-module-name

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L15 Redundant module name <record id="broken_module.view_model_form2" better using only <record id="view_model_form2"

 * xml-view-dangerous-replace-low-priority

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L25 Dangerous use of "replace" from view with priority 0 < 99
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L37 Dangerous use of "replace" from view with priority 0 < 99
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L47 Dangerous use of "replace" from view with priority 0 < 99
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L70 Dangerous use of "replace" from view with priority 10 < 99
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L92 Dangerous use of "replace" from view with priority 10 < 99
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L108 Dangerous use of "replace" from view with priority 10 < 99

 * xml-deprecated-tree-attribute

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo.xml#L31 Deprecated "<tree string=..."
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo.xml#L42 Deprecated "<tree colors=..."
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo.xml#L53 Deprecated "<tree fonts=..."

 * xml-dangerous-filter-wo-user

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo.xml#L60 Dangerous filter without explicit `user_id`

 * xml-duplicate-record-id

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view.xml#L5 Duplicate xml record id "data/view_model_form_noupdate_0" in test_repo/broken_module/model_view_odoo.xml:5, test_repo/broken_module/model_view_odoo2.xml:5
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L5 Duplicate xml record id "data/view_model_form2_noupdate_0" in test_repo/broken_module/model_view_odoo2.xml:17
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view2.xml#L103 Duplicate xml record id "data/view_model_form80_noupdate_0" in test_repo/broken_module/skip_xml_check.xml:5, test_repo/broken_module/skip_xml_check.xml:9, test_repo/broken_module/skip_xml_check_3.xml:6, test_repo/broken_module/skip_xml_check_3.xml:10

 * xml-duplicate-fields

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L6 Duplicate xml field "name" in lines 13
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L41 Duplicate xml field "key_config" in lines 42
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L73 Duplicate xml field "arch" in lines 76
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L79 Duplicate xml field "user_id" in lines 81
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L80 Duplicate xml field "name" in lines 83
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L90 Duplicate xml field "date" in lines 93
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L91 Duplicate xml field "min_date" in lines 94
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L132 Duplicate xml field "name" in lines 133
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/model_view_odoo2.xml#L138 Duplicate xml field "name" in lines 139

 * xml-syntax-error

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/file_no_exist.xml#L1 [Errno 2] No such file or directory: '/Users/moylop260/odoo/odoo-pre-commit-hooks/test_repo/broken_module/file_no_exist.xml'
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/broken_module/file_no_exist.xml#L1 [Errno 2] No such file or directory: '/Users/moylop260/odoo/odoo-pre-commit-hooks/test_repo/broken_module/file_no_exist.xml'

 * manifest-syntax-error

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/manifest_werror/__manifest__.py#L1 could not be loaded manifest malformed

 * csv-syntax-error

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/syntax_err_module/ir.model.access.csv#L1 'utf-8' codec can't decode byte 0xf1 in position 47: invalid continuation byte

 * missing-readme

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/syntax_err_module/README.rst#L1 missed file. Template here: https://github.com/OCA/maintainer-tools/blob/master/template/module/README.rst

 * po-syntax-error

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/syntax_err_module/i18n/es.po#L1 Syntax error in po file (line 19)

 * xml-deprecated-data-node

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/test_module/model_view.xml#L2 Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` instead of `<odoo><data noupdate="1">`

 * xml-deprecated-openerp-xml-node

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/test_module/res_users.xml#L2 Deprecated <openerp> xml node
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/test_module/model_view.xml#L2 Deprecated <openerp> xml node

 * xml-deprecated-qweb-directive

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/test_module/website_templates.xml#L7 Deprecated QWeb directive "t-esc-options". Use "t-options" instead
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/test_module/website_templates.xml#L14 Deprecated QWeb directive "t-field-options". Use "t-options" instead

 * xml-not-valid-char-link

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/test_module/website_templates.xml#L21 The resource in in src/href contains a not valid character
    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/test_module/website_templates.xml#L23 The resource in in src/href contains a not valid character

 * xml-create-user-wo-reset-password

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/test_module/res_users.xml#L10 record res.users without context="{'no_reset_password': True}"

 * manifest-syntax-error

    - https://github.com/OCA/odoo-pre-commit-hooks/blob/v0.0.9/test_repo/woinit_module/__manifest__.py#L1 could not be loaded

[//]: # (end-example)

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

----
OCA, or the [Odoo Community Association](http://odoo-community.org/), is a nonprofit
organization whose mission is to support the collaborative development of Odoo features
and promote its widespread use.

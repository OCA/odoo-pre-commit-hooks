import os
import re
from collections import defaultdict

from lxml import etree

from oca_pre_commit_hooks import utils

DFTL_MIN_PRIORITY = 99
DFLT_DEPRECATED_TREE_ATTRS = ["colors", "fonts", "string"]


class ChecksOdooModuleXML:
    def __init__(self, manifest_datas, module_name, enable, disable):
        self.module_name = module_name
        self.enable = enable
        self.disable = disable
        self.manifest_datas = manifest_datas
        self.checks_errors = defaultdict(list)
        for manifest_data in manifest_datas:
            try:
                with open(manifest_data["filename"], "rb") as f_xml:
                    manifest_data.update(
                        {
                            "node": etree.parse(f_xml),
                            "file_error": None,
                        }
                    )
            except (FileNotFoundError, etree.XMLSyntaxError, UnicodeDecodeError) as xml_err:
                manifest_data.update(
                    {
                        "node": etree.Element("__empty__"),
                        "file_error": str(xml_err).replace(manifest_data["filename"], ""),
                    }
                )

    @staticmethod
    def _get_priority(view):
        try:
            priority_node = view.xpath("field[@name='priority'][1]")[0]
            return int(priority_node.get("eval", priority_node.text) or 0)
        except (IndexError, ValueError):
            # IndexError: If the field is not found
            # ValueError: If the value found is not valid integer
            return 0

    @staticmethod
    def _is_replaced_field(view):
        try:
            arch = view.xpath("field[@name='arch' and @type='xml'][1]")[0]
        except IndexError:
            return False
        replaces = arch.xpath(".//field[@name='name' and @position='replace'][1] | .//*[@position='replace'][1]")
        return bool(replaces)

    def check_xml_records(self):
        """* Check xml-duplicate-record-id

        If a module has duplicated record_id AKA xml_ids
        file1.xml
            <record id="xmlid_name1"
        file2.xml
            <record id="xmlid_name1"

        * Check xml-duplicate-fields in all record nodes
            <record id="xmlid_name1"...
                <field name="field_name1"...
                <field name="field_name1"...
        """
        xmlids_section = defaultdict(list)
        xml_fields = defaultdict(list)
        for manifest_data in self.manifest_datas:
            for record in manifest_data["node"].xpath("/odoo//record[@id] | /openerp//record[@id]"):
                record_id = record.get("id")
                # xmlids_duplicated
                xmlid_key = (
                    f"{manifest_data['data_section']}/{record_id}"
                    f"_noupdate_{record.getparent().get('noupdate', '0')}"
                )
                xmlids_section[xmlid_key].append((manifest_data, record))

                # fields_duplicated
                if not record.xpath('field[@name="inherit_id"]'):
                    for field in record.xpath(
                        "field[@name] | field/*/field[@name] | "
                        "field/*/field/tree/field[@name] | "
                        "field/*/field/form/field[@name]"
                    ):
                        field_key = (
                            field.get("name"),
                            field.get("context"),
                            field.get("filter_domain"),
                            field.getparent(),
                        )
                        xml_fields[field_key].append((manifest_data, field))

                for meth in utils.getattr_checks(self, self.enable, self.disable, "visit_xml_record"):
                    meth(manifest_data, record)

        # xmlids_duplicated
        for xmlid_key, records in xmlids_section.items():
            if len(records) < 2:
                continue
            lines_str = ", ".join(f"{record[0]['filename_short']}:{record[1].sourceline}" for record in records[1:])
            self.checks_errors["xml-duplicate-record-id"].append(
                f"{records[0][0]['filename_short']}:{records[0][1].sourceline} "
                f'Duplicate xml record id "{xmlid_key}" in {lines_str}'
            )

        # fields_duplicated
        for field_key, fields in xml_fields.items():
            if len(fields) < 2:
                continue
            lines_str = ", ".join(f"{field[1].sourceline}" for field in fields[1:])
            self.checks_errors["xml-duplicate-fields"].append(
                f"{fields[0][0]['filename_short']}:{fields[0][1].sourceline} "
                f'Duplicate xml field "{field_key[0]}" in lines {lines_str}'
            )

    @utils.only_required_for_checks("xml-syntax-error")
    def check_xml_syntax_error(self):
        """* Check xml-syntax-error
        Check syntax of XML files declared in the Odoo manifest"""
        for manifest_data in self.manifest_datas:
            if not manifest_data["file_error"]:
                continue
            self.checks_errors["xml-syntax-error"].append(
                f'{manifest_data["filename_short"]}:1 {manifest_data["file_error"]}'
            )

    @utils.only_required_for_checks("xml-redundant-module-name")
    def visit_xml_record(self, manifest_data, record):
        """* Check xml-redundant-module-name

        If the module is called "module_a" and the xmlid is
        `<record id="module_a.xmlid_name1" ...`

        The "module_a." is redundant it could be replaced to only
        `<record id="xmlid_name1" ...`
        """
        # redundant_module_name
        record_id = record.get("id")
        xmlid_module, xmlid_name = record_id.split(".") if "." in record_id else ["", record_id]
        if xmlid_module == self.module_name:
            # TODO: Add autofix option
            self.checks_errors["xml-redundant-module-name"].append(
                f'{manifest_data["filename_short"]}:{record.sourceline} Redundant module'
                f' name `<record id="{record_id}"` '
                f'better using only `<record id="{xmlid_name}"`'
            )

    @utils.only_required_for_checks("xml-view-dangerous-replace-low-priority", "xml-deprecated-tree-attribute")
    def visit_xml_record_view(self, manifest_data, record):
        """* Check xml-view-dangerous-replace-low-priority in ir.ui.view

            <field name="priority" eval="10"/>
            ...
                <field name="name" position="replace"/>

        * Check xml-deprecated-tree-attribute
          The tree-view declaration is using a deprecated attribute.
        """
        if record.get("model") != "ir.ui.view":
            return
        # view_dangerous_replace_low_priority
        priority = self._get_priority(record)
        is_replaced_field = self._is_replaced_field(record)
        # TODO: Add self.config.min_priority instead of DFTL_MIN_PRIORITY
        if is_replaced_field and priority < DFTL_MIN_PRIORITY:
            self.checks_errors["xml-view-dangerous-replace-low-priority"].append(
                f'{manifest_data["filename_short"]}:{record.sourceline} '
                'Dangerous use of "replace" from view '
                f"with priority {priority} < {DFTL_MIN_PRIORITY}"
            )

        # deprecated_tree_attribute
        deprecate_attrs = {"string", "colors", "fonts"}
        xpath = f".//tree[{'|'.join(f'@{a}' for a in deprecate_attrs)}]"
        for deprecate_attr_node in record.xpath(xpath):
            deprecate_attr_str = ",".join(set(deprecate_attr_node.attrib.keys()) & deprecate_attrs)
            self.checks_errors["xml-deprecated-tree-attribute"].append(
                f'{manifest_data["filename_short"]}:{deprecate_attr_node.sourceline} '
                f'Deprecated "<tree {deprecate_attr_str}=..."'
            )

    @utils.only_required_for_checks("xml-create-user-wo-reset-password")
    def visit_xml_record_user(self, manifest_data, record):
        """* Check xml-create-user-wo-reset-password
        records of user without `context="{'no_reset_password': True}"`
        This context avoid send email and mail log warning
        """
        # xml_create_user_wo_reset_password
        if record.get("model") != "res.users":
            return
        if record.xpath("field[@name='name'][1]") and "no_reset_password" not in (record.get("context") or ""):
            # if exists field="name" then is a new record
            # then should be context
            self.checks_errors["xml-create-user-wo-reset-password"].append(
                f'{manifest_data["filename_short"]}:{record.sourceline} '
                "record res.users without "
                "`context=\"{'no_reset_password': True}\"`"
            )

    @utils.only_required_for_checks("xml-dangerous-filter-wo-user")
    def visit_xml_record_filter(self, manifest_data, record):
        """* Check xml-dangerous-filter-wo-user
        Check dangerous filter without a user assigned.
        """
        # xml_dangerous_filter_wo_user
        if record.get("model") != "ir.filters":
            return
        ir_filter_fields = record.xpath("field[@name='name' or @name='user_id']")
        # if exists field="name" then is a new record
        # then should be field="user_id" too
        if ir_filter_fields and len(ir_filter_fields) == 1:
            self.checks_errors["xml-dangerous-filter-wo-user"].append(
                f'{manifest_data["filename_short"]}:{record.sourceline} ' "Dangerous filter without explicit `user_id`"
            )

    @utils.only_required_for_checks("xml-not-valid-char-link")
    def check_xml_not_valid_char_link(self):
        """* Check xml-not-valid-char-link
        The resource in in src/href contains a not valid character."""
        for manifest_data in self.manifest_datas:
            for name, attr in (("link", "href"), ("script", "src")):
                nodes = manifest_data["node"].xpath(f".//{name}[@{attr}]")
                for node in nodes:
                    resource = node.get(attr, "")
                    ext = os.path.splitext(os.path.basename(resource))[1]
                    if resource.startswith("/") and not re.search("^[.][a-zA-Z]+$", ext):
                        self.checks_errors["xml-not-valid-char-link"].append(
                            f'{manifest_data["filename_short"]}:{node.sourceline} '
                            f"The resource in in src/href contains a not valid character"
                        )

    @utils.only_required_for_checks("xml-dangerous-qweb-replace-low-priority")
    def check_xml_dangerous_qweb_replace_low_priority(self):
        """* Check xml-dangerous-qweb-replace-low-priority
        Dangerous qweb view defined with low priority"""
        for manifest_data in self.manifest_datas:
            for template in manifest_data["node"].xpath("/odoo//template|/openerp//template"):
                try:
                    priority = int(template.get("priority"))
                except (ValueError, TypeError):
                    priority = 0
                for child in template.iterchildren():
                    # TODO: Add self.config.min_priority instead of DFTL_MIN_PRIORITY
                    if child.get("position") == "replace" and priority < DFTL_MIN_PRIORITY:
                        self.checks_errors["xml-dangerous-qweb-replace-low-priority"].append(
                            f'{manifest_data["filename_short"]}:{child.sourceline} '
                            'Dangerous use of "replace" from view '
                            f"with priority `{priority} < {DFTL_MIN_PRIORITY}`"
                        )

    @utils.only_required_for_checks("xml-deprecated-data-node")
    def check_xml_deprecated_data_node(self):
        """* Check xml-deprecated-data-node
        Deprecated <data> node inside <odoo> xml node"""
        for manifest_data in self.manifest_datas:
            for odoo_node in manifest_data["node"].xpath("/odoo|/openerp"):
                children_count = 0
                for children_count, _ in enumerate(odoo_node.iterchildren(), start=1):
                    if children_count == 2:
                        # Only needs to know if there are more than one child
                        break
                # if "broken_module/model_view_odoo2.xml" in manifest_data["filename"]:
                #     import pdb;pdb.set_trace()
                if children_count == 1 and len(odoo_node.xpath("./data")) == 1:
                    # TODO: Add autofix option
                    self.checks_errors["xml-deprecated-data-node"].append(
                        f'{manifest_data["filename_short"]}:{odoo_node.sourceline} '
                        'Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` '
                        'instead of `<odoo><data noupdate="1">`'
                    )

    @utils.only_required_for_checks("xml-deprecated-openerp-xml-node")
    def check_xml_deprecated_openerp_node(self):
        """* Check xml-deprecated-openerp-xml-node
        deprecated <openerp> xml node"""
        for manifest_data in self.manifest_datas:
            for openerp_node in manifest_data["node"].xpath("/openerp"):
                # TODO: Add autofix option
                self.checks_errors["xml-deprecated-openerp-xml-node"].append(
                    f'{manifest_data["filename_short"]}:{openerp_node.sourceline} ' "Deprecated <openerp> xml node"
                )

    @utils.only_required_for_checks("xml-deprecated-qweb-directive")
    def check_xml_deprecated_qweb_directive(self):
        """* Check xml-deprecated-qweb-directive
        for use of deprecated QWeb directives t-*-options"""
        deprecated_directives = {
            "t-esc-options",
            "t-field-options",
            "t-raw-options",
        }
        deprecated_attrs = "|".join(f"@{d}" for d in deprecated_directives)
        xpath = f"/odoo//template//*[{deprecated_attrs}] | " f"/openerp//template//*[{deprecated_attrs}]"

        for manifest_data in self.manifest_datas:
            for node in manifest_data["node"].xpath(xpath):
                directive_str = ", ".join(set(node.attrib) & deprecated_directives)
                self.checks_errors["xml-deprecated-qweb-directive"].append(
                    f'{manifest_data["filename_short"]}:{node.sourceline} '
                    f'Deprecated QWeb directive `"{directive_str}"`. Use `"t-options"` instead'
                )

import os
import re
from collections import defaultdict

from lxml import etree

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.base_checker import BaseChecker

DFTL_MIN_PRIORITY = 99
DFLT_DEPRECATED_TREE_ATTRS = ["colors", "fonts", "string"]


# Same as Odoo: https://github.com/odoo/odoo/commit/9cefa76988ff94c3d590c6631b604755114d0297
def _hasclass(context, *cls):
    """Checks if the context node has all the classes passed as arguments"""
    node_classes = set(context.context_node.attrib.get("class", "").split())
    return node_classes.issuperset(cls)


etree.FunctionNamespace(None)["hasclass"] = _hasclass


class ChecksOdooModuleXML(BaseChecker):
    xpath_deprecated_data = etree.XPath("/odoo[count(./*) < 2]/data|/openerp[count(./*) < 2]/data")
    xpath_oe_structure_woid = etree.XPath(
        "//*[hasclass('oe_structure') and (not(@id) or not(contains(@id, 'oe_structure')))]"
    )
    xpath_record_wid = etree.XPath("/odoo//record[@id] | /openerp//record[@id]")
    xpath_view_arch_xml = etree.XPath("field[@name='arch' and @type='xml'][1]")
    xpath_ir_fields = etree.XPath("field[@name='name' or @name='user_id']")
    xpath_template = etree.XPath("/odoo//template|/openerp//template")
    xpath_view_replaces = etree.XPath(".//*[@position='replace'][1]")
    xpath_char_links = etree.XPath(".//link[@href]|.//script[@src]")
    xpath_view_priority = etree.XPath("field[@name='priority'][1]")
    xpath_field_name = etree.XPath("field[@name='name'][1]")
    xpath_record_fields_wname = etree.XPath("field[@name]")
    xpath_comment = etree.XPath("//comment()")
    xpath_openerp = etree.XPath("/openerp")
    xpath_xpath = etree.XPath("//xpath")

    tree_deprecate_attrs = {"string", "colors", "fonts"}
    xpath_tree_deprecated = etree.XPath(f'.//tree[{"|".join(f"@{a}" for a in tree_deprecate_attrs)}]')

    qweb_deprecated_directives = {
        "t-esc-options",
        "t-field-options",
        "t-raw-options",
    }
    qweb_deprecated_attrs = "|".join(f"@{d}" for d in qweb_deprecated_directives)
    xpath_qweb_deprecated = etree.XPath(
        f"/odoo//template//*[{qweb_deprecated_attrs}] | " f"/openerp//template//*[{qweb_deprecated_attrs}]"
    )

    def __init__(self, manifest_datas, module_name, enable, disable):
        super().__init__(enable, disable, module_name)
        self.manifest_datas = manifest_datas
        for manifest_data in self.manifest_datas:
            try:
                with open(manifest_data["filename"], "rb") as f_xml:
                    node = etree.parse(f_xml)
                    manifest_data.update(
                        {
                            "node": node,
                            "file_error": None,
                            "disabled_checks": self._get_disabled_checks(node),
                        }
                    )
            except (FileNotFoundError, etree.XMLSyntaxError, UnicodeDecodeError) as xml_err:
                manifest_data.update(
                    {
                        "node": etree.Element("__empty__"),
                        "file_error": str(xml_err).replace(manifest_data["filename"], ""),
                        "disabled_checks": set(),
                    }
                )

    def _get_disabled_checks(self, node):
        """Get the check-name disable comments from etree XML node

        e.g. <!-- oca-hooks:disable=check-name -->
        """
        all_checks_disabled = set()
        for comment_node in self.xpath_comment(node):
            checks_disabled, use_deprecated = utils.checks_disabled(comment_node.text)
            all_checks_disabled |= set(checks_disabled)
            if use_deprecated:
                print(f"{node.docinfo.URL}:{comment_node.sourceline} WARNING. DEPRECATED. Use oca-disable instead.")
        return all_checks_disabled

    def getattr_checks(self, manifest_data, prefix):
        disable_node = manifest_data["disabled_checks"]
        yield from utils.getattr_checks(self, self.enable, self.disable, prefix, disable_node)

    def is_message_enabled(self, checks, manifest_data):
        disable_node = manifest_data["disabled_checks"]
        return utils.is_message_enabled(checks, self.enable, self.disable, disable_node)

    @classmethod
    def _get_priority(cls, view):
        try:
            priority_node = cls.xpath_view_priority(view)[0]
            return int(priority_node.get("eval", priority_node.text) or 0)
        except (IndexError, ValueError):
            # IndexError: If the field is not found
            # ValueError: If the value found is not valid integer
            return 0

    @classmethod
    def _is_replaced_field(cls, view):
        try:
            arch = cls.xpath_view_arch_xml(view)[0]
        except IndexError:
            return False
        replaces = cls.xpath_view_replaces(arch)
        return bool(replaces)

    # Not set only_required_for_checks because of the calls to visit_xml_record... methods
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
            for record in self.xpath_record_wid(manifest_data["node"]):
                record_id = record.get("id")

                if self.is_message_enabled("xml-duplicate-record-id", manifest_data):
                    # xmlids_duplicated
                    xmlid_key = (
                        f"{manifest_data['data_section']}/{record_id}"
                        f"_noupdate_{record.getparent().get('noupdate', '0')}"
                    )
                    xmlids_section[xmlid_key].append((manifest_data, record))

                # fields_duplicated
                if self.is_message_enabled("xml-duplicate-fields", manifest_data):
                    for field in self.xpath_record_fields_wname(record):
                        xml_fields[(field.get("name"), field.getparent())].append((manifest_data, field))

                # call "visit_xml_record_*" methods to re-use the same node xpath loop
                for meth in self.getattr_checks(manifest_data, "visit_xml_record"):
                    meth(manifest_data, record)

        # xmlids_duplicated (empty dict if check is not enabled)
        for xmlid_key, records in xmlids_section.items():
            if len(records) < 2:
                continue
            lines_str = ", ".join(f"{record[0]['filename_short']}:{record[1].sourceline}" for record in records[1:])
            self.checks_errors["xml-duplicate-record-id"].append(
                f"{records[0][0]['filename_short']}:{records[0][1].sourceline} "
                f'Duplicate xml record id "{xmlid_key}" in {lines_str}'
            )

        # fields_duplicated (empty dict if check is not enabled)
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
                f"with priority {priority} < {DFTL_MIN_PRIORITY}. "
                'Only replace as a last resort. Try position="attributes", position="move" or invisible="1" first'
            )

        # deprecated_tree_attribute
        for deprecate_attr_node in self.xpath_tree_deprecated(record):
            deprecate_attr_str = ",".join(set(deprecate_attr_node.attrib.keys()) & self.tree_deprecate_attrs)
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
        ir_filter_fields = self.xpath_ir_fields(record)
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
            if not self.is_message_enabled("xml-not-valid-char-link", manifest_data):
                continue

            for node in self.xpath_char_links(manifest_data["node"]):
                resource = node.get("href", "") or node.get("src", "")
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
            if not self.is_message_enabled("xml-dangerous-qweb-replace-low-priority", manifest_data):
                continue
            for template in self.xpath_template(manifest_data["node"]):
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
                            f"with priority `{priority} < {DFTL_MIN_PRIORITY}`. "
                            "Only replace as a last resort. "
                            'Try position="attributes", position="move" or t-if="False" first'
                        )

    @utils.only_required_for_checks("xml-deprecated-data-node")
    def check_xml_deprecated_data_node(self):
        """* Check xml-deprecated-data-node
        Deprecated <data> node inside <odoo> xml node"""
        for manifest_data in self.manifest_datas:
            if not self.is_message_enabled("xml-deprecated-data-node", manifest_data):
                continue
            for data_node in self.xpath_deprecated_data(manifest_data["node"]):
                # TODO: Add autofix option
                self.checks_errors["xml-deprecated-data-node"].append(
                    f'{manifest_data["filename_short"]}:{data_node.sourceline} '
                    'Use `<odoo>` instead of `<odoo><data>` or use `<odoo noupdate="1">` '
                    'instead of `<odoo><data noupdate="1">`'
                )

    @utils.only_required_for_checks("xml-deprecated-openerp-node")
    def check_xml_deprecated_openerp_node(self):
        """* Check xml-deprecated-openerp-node
        deprecated <openerp> xml node"""
        for manifest_data in self.manifest_datas:
            if not self.is_message_enabled("xml-deprecated-openerp-node", manifest_data):
                continue
            for openerp_node in self.xpath_openerp(manifest_data["node"]):
                # TODO: Add autofix option
                self.checks_errors["xml-deprecated-openerp-node"].append(
                    f'{manifest_data["filename_short"]}:{openerp_node.sourceline} ' "Deprecated <openerp> xml node"
                )

    @utils.only_required_for_checks("xml-deprecated-qweb-directive")
    def check_xml_deprecated_qweb_directive(self):
        """* Check xml-deprecated-qweb-directive
        for use of deprecated QWeb directives t-*-options"""
        for manifest_data in self.manifest_datas:
            if not self.is_message_enabled("xml-deprecated-qweb-directive", manifest_data):
                continue
            for node in self.xpath_qweb_deprecated(manifest_data["node"]):
                directive_str = ", ".join(set(node.attrib) & self.qweb_deprecated_directives)
                self.checks_errors["xml-deprecated-qweb-directive"].append(
                    f'{manifest_data["filename_short"]}:{node.sourceline} '
                    f'Deprecated QWeb directive `"{directive_str}"`. Use `"t-options"` instead'
                )

    @utils.only_required_for_checks("xml-xpath-translatable-item")
    def check_xml_xpath(self):
        """* Check xml-xpath-translatable-item check `xpath` nodes using `contains(text(), 'Text translatable')`
        Since that the text could be translated so it is a mutable value.
        It could raise `ValueError` exception if the language is changed.
        """
        for manifest_data in self.manifest_datas:
            for xpath_node in self.xpath_xpath(manifest_data["node"]):
                node_expr = (xpath_node.get("expr") or "").replace(" ", "")
                if "[contains(text()" in node_expr or "[text()=" in node_expr:
                    self.checks_errors["xml-xpath-translatable-item"].append(
                        f'{manifest_data["filename_short"]}:{xpath_node.sourceline} '
                        f"Use of translatable xpath `text()`"
                    )

    @utils.only_required_for_checks("xml-oe-structure-missing-id")
    def check_xml_oe_structure(self):
        """* Check xml-oe-structure-missing-id

        Ensure all tags with class 'oe_structure' have an ID. For more information on the rationale, see:
        https://github.com/OCA/odoo-pre-commit-hooks/issues/27
        """
        for manifest_data in self.manifest_datas:
            for xpath_node in self.xpath_oe_structure_woid(manifest_data["node"]):
                self.checks_errors["xml-oe-structure-missing-id"].append(
                    f'{manifest_data["filename_short"]}:{xpath_node.sourceline} '
                    "Consider removing the class 'oe_structure' or adding a proper id to the tag. The id must contain "
                    "'oe_structure'"
                )

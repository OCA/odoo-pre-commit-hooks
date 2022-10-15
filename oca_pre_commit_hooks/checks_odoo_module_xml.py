import os
import re
from collections import defaultdict

from lxml import etree

DFTL_MIN_PRIORITY = 99
DFLT_DEPRECATED_TREE_ATTRS = ["colors", "fonts", "string"]


class ChecksOdooModuleXML:
    def __init__(self, manifest_xmls, module_name):
        self.module_name = module_name
        self.manifest_xmls = manifest_xmls
        for manifest_xml in manifest_xmls:
            try:
                with open(manifest_xml["filename"], "rb") as f_xml:
                    manifest_xml.update(
                        {
                            "node": etree.parse(f_xml),
                            "file_error": None,
                        }
                    )
            except (FileNotFoundError, etree.XMLSyntaxError) as xml_err:
                # xml syntax error is raised from another hook
                manifest_xml.update(
                    {
                        "node": etree.Element("__empty__"),
                        "file_error": xml_err,
                    }
                )
        self.checks_errors = defaultdict(list)

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
        replaces = arch.xpath(
            ".//field[@name='name' and @position='replace'][1] | .//*[@position='replace'][1]"
        )
        return bool(replaces)

    def check_xml_records(self):
        """* Check xml_redundant_module_name

        If the module is called "module_a" and the xmlid is
        <record id="module_a.xmlid_name1" ...

        The "module_a." is redundant it could be replaced to only
        <record id="xmlid_name1" ...

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

        * Check xml_view_dangerous_replace_low_priority in ir.ui.view
            <field name="priority" eval="10"/>
            ...
                <field name="name" position="replace"/>

        * Check xml_create_user_wo_reset_password
            records of user without context="{'no_reset_password': True}"
            This context avoid send email and mail log warning

        * Check xml_dangerous_filter_wo_user
        Check dangerous filter without a user assigned.

        * Check xml_deprecated_tree_attribute
        The tree-view declaration is using a deprecated attribute.
        """
        xmlids_section = defaultdict(list)
        xml_fields = defaultdict(list)
        for manifest_xml in self.manifest_xmls:
            for record in manifest_xml["node"].xpath(
                "/odoo//record[@id] | /openerp//record[@id]"
            ):
                record_id = record.get("id")
                # xmlids_duplicated
                xmlid_key = (
                    f"{manifest_xml['data_section']}/{record_id}"
                    f"_noupdate_{record.getparent().get('noupdate', '0')}"
                )
                xmlids_section[xmlid_key].append(record)

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
                        xml_fields[field_key].append(field)

                # redundant_module_name
                xmlid_module, xmlid_name = (
                    record_id.split(".") if "." in record_id else ["", record_id]
                )
                if xmlid_module == self.module_name:
                    # TODO: Add autofix option
                    self.checks_errors["xml_redundant_module_name"].append(
                        f'{manifest_xml["filename"]}:{record.sourceline} Redundant module'
                        f' name <record id="{record_id}" '
                        f'better using only <record id="{xmlid_name}"'
                    )

                if record.get("model") == "ir.ui.view":
                    # view_dangerous_replace_low_priority
                    priority = self._get_priority(record)
                    is_replaced_field = self._is_replaced_field(record)
                    # TODO: Add self.config.min_priority instead of DFTL_MIN_PRIORITY
                    if is_replaced_field and priority < DFTL_MIN_PRIORITY:
                        self.checks_errors[
                            "xml_view_dangerous_replace_low_priority"
                        ].append(
                            f'{manifest_xml["filename"]}:{record.sourceline} '
                            'Dangerous use of "replace" from view '
                            f"with priority {priority} < {DFTL_MIN_PRIORITY}"
                        )

                    # deprecated_tree_attribute
                    deprecate_attrs = {"string", "colors", "fonts"}
                    xpath = f".//tree[{'|'.join(f'@{a}' for a in deprecate_attrs)}]"
                    for deprecate_attr_node in record.xpath(xpath):
                        deprecate_attr_str = ",".join(
                            set(deprecate_attr_node.attrib.keys()) & deprecate_attrs
                        )
                        self.checks_errors["xml_deprecated_tree_attribute"].append(
                            f'{manifest_xml["filename"]}:{deprecate_attr_node.sourceline} '
                            f'Deprecated "<tree {deprecate_attr_str}=..."'
                        )

                # xml_create_user_wo_reset_password
                if (
                    record.get("model") == "res.users"
                    and record.xpath("field[@name='name'][1]")
                    and "no_reset_password" not in (record.get("context") or "")
                ):
                    # if exists field="name" then is a new record
                    # then should be context
                    self.checks_errors["xml_create_user_wo_reset_password"].append(
                        f'{manifest_xml["filename"]}:{record.sourceline} '
                        "record res.users without "
                        "context=\"{'no_reset_password': True}\""
                    )

                # xml_dangerous_filter_wo_user
                if record.get("model") == "ir.filters":
                    ir_filter_fields = record.xpath(
                        "field[@name='name' or @name='user_id']"
                    )
                    # if exists field="name" then is a new record
                    # then should be field="user_id" too
                    if ir_filter_fields and len(ir_filter_fields) == 1:
                        self.checks_errors["xml_dangerous_filter_wo_user"].append(
                            f'{manifest_xml["filename"]}:{record.sourceline} '
                            "Dangerous filter without explicit `user_id`"
                        )

        # xmlids_duplicated
        for xmlid_key, records in xmlids_section.items():
            if len(records) < 2:
                continue
            # FIXME: manifest_xml is a variable used in the loop
            self.checks_errors["xml_duplicate_record_id"].append(
                f'{manifest_xml["filename"]}:{records[0].sourceline} '
                f'Duplicate xml record id "{xmlid_key}" in '
                f'{", ".join(f"{record.base}:{record.sourceline}" for record in records[1:])}'
            )

        # fields_duplicated
        for field_key, fields in xml_fields.items():
            if len(fields) < 2:
                continue
            self.checks_errors["xml_duplicate_fields"].append(
                f'{manifest_xml["filename"]}:{fields[0].sourceline} '
                f'Duplicate xml field "{field_key[0]}" in lines '
                f'{", ".join(f"{field.sourceline}" for field in fields[1:])}'
            )

    def check_xml_not_valid_char_link(self):
        """The resource in in src/href contains a not valid character"""
        for manifest_xml in self.manifest_xmls:
            for name, attr in (("link", "href"), ("script", "src")):
                nodes = manifest_xml["node"].xpath(".//%s[@%s]" % (name, attr))
                for node in nodes:
                    resource = node.get(attr, "")
                    ext = os.path.splitext(os.path.basename(resource))[1]
                    if resource.startswith("/") and not re.search(
                        "^[.][a-zA-Z]+$", ext
                    ):
                        self.checks_errors["check_xml_not_valid_char_link"].append(
                            f'{manifest_xml["filename"]}:{node.sourceline} '
                            f"The resource in in src/href contains a not valid character"
                        )

    def check_xml_dangerous_qweb_replace_low_priority(self):
        """Check dangerous qweb view defined with low priority"""
        for manifest_xml in self.manifest_xmls:
            for template in manifest_xml["node"].xpath(
                "/odoo//template|/openerp//template"
            ):
                try:
                    priority = int(template.get("priority"))
                except (ValueError, TypeError):
                    priority = 0
                for child in template.iterchildren():
                    # TODO: Add self.config.min_priority instead of DFTL_MIN_PRIORITY
                    if (
                        child.get("position") == "replace"
                        and priority < DFTL_MIN_PRIORITY
                    ):
                        self.checks_errors[
                            "xml_dangerous_qweb_replace_low_priority"
                        ].append(
                            f'{manifest_xml["filename"]}:{template.sourceline} '
                            'Dangerous use of "replace" from view '
                            f"with priority {priority} < {DFTL_MIN_PRIORITY}"
                        )

    def check_xml_deprecated_data_node(self):
        """Check deprecated <data> node inside <odoo> xml node"""
        for manifest_xml in self.manifest_xmls:
            for odoo_node in manifest_xml["node"].xpath("/odoo"):
                for children_count, _ in enumerate(odoo_node.iterchildren(), start=1):
                    if children_count == 2 and len(odoo_node.xpath("/data")) == 1:
                        # TODO: Add autofix option
                        self.checks_errors["xml_deprecated_data_node"].append(
                            f'{manifest_xml["filename"]}:{odoo_node.sourceline} '
                            'Use <odoo> instead of <odoo><data> or use <odoo noupdate="1"> '
                            'instead of <odoo><data noupdate="1">'
                        )
                        break

    def check_xml_deprecated_openerp_node(self):
        """Check deprecated <openerp> xml node"""
        for manifest_xml in self.manifest_xmls:
            for openerp_node in manifest_xml["node"].xpath("/openerp"):
                # TODO: Add autofix option
                self.checks_errors["xml_deprecated_openerp_xml_node"].append(
                    f'{manifest_xml["filename"]}:{openerp_node.sourceline} '
                    "Deprecated <openerp> xml node"
                )

    def check_xml_deprecated_qweb_directive(self):
        """Check for use of deprecated QWeb directives t-*-options."""
        deprecated_directives = {
            "t-esc-options",
            "t-field-options",
            "t-raw-options",
        }
        deprecated_attrs = "|".join("@%s" % d for d in deprecated_directives)
        xpath = (
            f"/odoo//template//*[{deprecated_attrs}] | "
            f"/openerp//template//*[{deprecated_attrs}]"
        )

        for manifest_xml in self.manifest_xmls:
            for node in manifest_xml["node"].xpath(xpath):
                directive_str = ", ".join(set(node.attrib) & deprecated_directives)
                self.checks_errors["xml_deprecated_qweb_directive"].append(
                    f'{manifest_xml["filename"]}:{node.sourceline} '
                    f'Deprecated QWeb directive "{directive_str}". Use "t-options" instead'
                )

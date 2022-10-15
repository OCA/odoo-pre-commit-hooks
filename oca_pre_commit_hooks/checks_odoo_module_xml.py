# Hooks are using print directly
# pylint: disable=print-used
import os
import re
from collections import defaultdict

from lxml import etree

DFTL_MIN_PRIORITY = 99


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
                            "node_error": None,
                        }
                    )
            except (FileNotFoundError, etree.XMLSyntaxError) as xml_err:
                # xml syntax error is raised from another hook
                manifest_xml.update(
                    {
                        "node": None,
                        "node_error": xml_err,
                    }
                )
        self.checks_errors = defaultdict(list)

    @staticmethod
    def _get_priority(view):
        try:
            priority_node = view.xpath("field[@name='priority'][1]")[0]
            return int(priority_node.get("eval", priority_node.text) or 0)
        except (IndexError, ValueError):  # pylint: disable=except-pass
            # IndexError: If the field is not found
            # ValueError: If the value found is not valid integer
            pass
        return 0

    @staticmethod
    def _is_replaced_field(view):
        try:
            arch = view.xpath("field[@name='arch' and @type='xml'][1]")[0]
        except IndexError:
            return None
        replaces = arch.xpath(
            ".//field[@name='name' and @position='replace'][1]"
        ) + arch.xpath(".//*[@position='replace'][1]")
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
        """
        xmlids_section = defaultdict(list)
        xml_fields = defaultdict(list)
        for manifest_xml in self.manifest_xmls:
            if not manifest_xml["node"]:
                continue
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
                xmlid_module, xmlid_name = (
                    record_id.split(".") if "." in record_id else ["", record_id]
                )

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
                # TODO: Add autofix option
                if xmlid_module == self.module_name:
                    self.checks_errors["xml_redundant_module_name"].append(
                        f'{manifest_xml["filename"]}:{record.sourceline} Redundant module'
                        f' name <record id="{record_id}" '
                        'better using only <record id="{xmlid_name}"'
                    )

                # view_dangerous_replace_low_priority
                if record.get("model") == "ir.ui.view":
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

        # xmlids_duplicated
        for xmlid_key, records in xmlids_section.items():
            if len(records) < 2:
                continue
            # TODO: Use relative path e.g. os.path.relpath(record.base, self.module_path)
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
            if not manifest_xml["node"]:
                continue
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

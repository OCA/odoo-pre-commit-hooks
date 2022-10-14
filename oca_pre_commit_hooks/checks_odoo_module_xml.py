# Hooks are using print directly
# pylint: disable=print-used

from collections import defaultdict

from lxml import etree


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

    def check_xml_records(self):
        """Check xml_redundant_module_name.

        If the module is called "module_a" and the xmlid is
        <record id="module_a.xmlid_name1" ...

        The "module_a." is redundant it could be replaced to only
        <record id="xmlid_name1" ...

        Check xml_duplicate_record_id

        If a module has duplicated record_id AKA xml_ids
        file1.xml
            <record id="xmlid_name1"
        file2.xml
            <record id="xmlid_name1"
        """
        # TODO: Add autofix option
        xmlids_section = defaultdict(list)
        for manifest_xml in self.manifest_xmls:
            if not manifest_xml["node"]:
                continue
            for record in manifest_xml["node"].xpath(
                "/odoo//record | /openerp//record"
            ):
                record_id = record.get("id")
                if not record_id:
                    continue
                xmlid_key = (
                    f"{manifest_xml['data_section']}/{record_id}"
                    f"_noupdate_{record.getparent().get('noupdate', '0')}"
                )
                xmlids_section[xmlid_key].append(record)
                xmlid_module, xmlid_name = (
                    record_id.split(".") if "." in record_id else ["", record_id]
                )
                if xmlid_module != self.module_name:
                    continue
                self.checks_errors["xml_redundant_module_name"].append(
                    f'{manifest_xml["filename"]}:{record.sourceline} Redundant module'
                    f' name <record id="{record_id}" '
                    'better using only <record id="{xmlid_name}"'
                )
        for xmlid_key, records in xmlids_section.items():
            if len(records) < 2:
                continue
            # TODO: Use relative path e.g. os.path.relpath(record.base, self.module_path)
            self.checks_errors["xml_duplicate_record_id"].append(
                f'{manifest_xml["filename"]}:{records[0].sourceline} '
                f'Duplicate xml record id "{xmlid_key}" in '
                f'{", ".join(f"{record.base}:{record.sourceline}" for record in records[1:])}'
            )

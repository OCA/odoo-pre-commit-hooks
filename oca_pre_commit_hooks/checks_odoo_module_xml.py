# Hooks are using print directly
# pylint: disable=print-used

from collections import defaultdict

from lxml import etree


def parsed(method):
    def inner(self):
        msg_tmpl = "Skipped check '%s' for '%s'" % (
            method.__name__,
            self.xml_manifest,
        )
        if not self.node:
            print("%s with error: '%s'" % (msg_tmpl, self.error))
        else:
            return method(self)

    return inner


class ChecksOdooModuleXML:
    def __init__(self, xml_manifest, module_name):
        self.module_name = module_name
        self.xml_manifest = xml_manifest
        self.error = None
        try:
            with open(xml_manifest["filename"], "rb") as f_xml:
                self.node = etree.parse(f_xml)
        except (FileNotFoundError, etree.XMLSyntaxError) as xml_err:
            # xml syntax error is raised from another hook
            self.node = None
            self.error = xml_err
        self.checks_errors = defaultdict(list)

    @parsed
    def check_xml_redundant_module_name(self):
        """Check redundant module name in odoo xml.

        If the module is called "module_a" and the xmlid is
        <record id="module_a.xmlid_name1" ...

        The "module_a." is redundant it could be replaced to only
        <record id="xmlid_name1" ...
        """
        # TODO: Add autofix option
        for record in self.node.xpath("/odoo//record") + self.node.xpath(
            "/openerp//record"
        ):
            record_id = record.get("id")
            if not record_id:
                continue
            xmlid_module, xmlid_name = (
                record_id.split(".") if "." in record_id else ["", record_id]
            )
            if xmlid_module != self.module_name:
                continue
            self.checks_errors["xml_redundant_module_name"].append(
                f'{self.xml_manifest["filename"]}:{record.sourceline} Redundant module'
                f' name <record id="{record_id}" '
                'better using only <record id="{xmlid_name}"'
            )

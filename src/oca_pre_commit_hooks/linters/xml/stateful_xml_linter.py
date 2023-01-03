import ast
import itertools
from os.path import basename, dirname, exists, join, pardir, relpath
from typing import Mapping, MutableMapping, Sequence, Set

from lxml import etree

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.linters.message import Message
from oca_pre_commit_hooks.linters.scheduler_configuration import SchedulerConfiguration
from oca_pre_commit_hooks.linters.xml.base_xml_linter import BaseXmlLinter


class StatefulXmlLinter(BaseXmlLinter):
    _messages = {"xml-duplicate-record-id": "Duplicate <record> id '%s' in %s"}

    def __init__(self):
        super().__init__()
        self.xml_ids: MutableMapping[str, Set] = {}
        self.processed_modules = []

    @classmethod
    def manifest_from_file(cls, file: str, max_attempts: int = 10) -> str:
        def try_attempts(directory: str):
            for name in cls.manifest_names:
                attempt = join(directory, name)
                if exists(attempt):
                    return attempt

            return False

        manifest = try_attempts(dirname(file))
        if manifest:
            return manifest

        search_dir = file
        for _i in range(max_attempts):
            search_dir = relpath(join(search_dir, pardir))
            manifest = try_attempts(search_dir)
            if manifest:
                return manifest

        return ""

    @staticmethod
    def xml_files_from_manifest(file: str) -> Mapping[str, Set[str]]:
        with open(file, encoding="utf-8") as manifest_fd:
            manifest = ast.literal_eval(manifest_fd.read())

        data_files = set()
        demo_files = set()
        manifest_root = dirname(file)
        for data_xml, demo_xml in itertools.zip_longest(manifest.get("data", []), manifest.get("demo", [])):
            if data_xml and data_xml.endswith(".xml"):
                data_files.add(join(manifest_root, data_xml))
            if demo_xml and demo_xml.endswith(".xml"):
                demo_files.add(join(manifest_root, demo_xml))

        return {"data": data_files, "demo": demo_files}

    def process_duplicate_xml_ids(self):
        for element_set in self.xml_ids.values():
            if len(element_set) == 1:
                continue

            original_element = element_set.pop()
            message_description = ""
            local_offenders = ""  # Elements contained in the same file as the original element.
            remote_offenders = ""  # All other elements
            for element in element_set:
                if element.base == original_element.base:
                    local_offenders += f"line {element.sourceline}, "
                else:
                    remote_offenders += f"{relpath(element.base)}:{element.sourceline}, "

            # Remove trailing coma and space
            local_offenders = local_offenders[:-2]
            remote_offenders = remote_offenders[:-2]
            if local_offenders:
                message_description += f"{local_offenders} and "
            if remote_offenders:
                message_description += f"files: {remote_offenders}"

            self.add_message(
                Message(
                    "xml-duplicate-record-id",
                    relpath(original_element.base),
                    (original_element.get("id"), message_description),
                    original_element.sourceline,
                )
            )

    def on_close(self):
        super().on_close()

        self.process_duplicate_xml_ids()
        self.xml_ids.clear()

    def generate_config(self, argv: Sequence[str]) -> SchedulerConfiguration:
        config = super().generate_config(argv)
        manifest_files = set()
        for file in config.filenames:
            manifest = self.manifest_from_file(file)
            if manifest:
                manifest_files.add(manifest)

        config.filenames = manifest_files

        return config

    def _check_loop(self, config: SchedulerConfiguration, file: str):
        module = basename(dirname(file))
        if module not in self.processed_modules:

            self.processed_modules.append(module)
            xml_files = self.xml_files_from_manifest(file)
            for xml_type, xml_files in xml_files.items():
                for xml in xml_files:
                    try:
                        with open(xml, encoding="utf-8") as xml_fd:
                            tree = etree.parse(xml_fd)
                    except (etree.XMLSyntaxError, UnicodeDecodeError, FileNotFoundError):
                        continue

                    checks = self.get_active_checks(
                        config.enable, config.disable | self.get_file_disabled_checks(tree)
                    )
                    for check in checks:
                        check(tree, module, xml_type)

    @utils.only_required_for_checks("xml-duplicate-record-id")
    def check_xml_duplicate_record_id(self, tree, module: str, xml_type: str):
        elements = tree.xpath("//record")
        for elem in elements:
            elem_id = elem.get("id")
            if not elem_id:
                continue  # This is an error, as these tags MUST have an id.

            data_type = elem.getparent().get("noupdate", "0")
            elem_id = f"{xml_type}{data_type}:{self.normalize_xml_id(elem_id, module)}"
            if elem_id in self.xml_ids:
                self.xml_ids[elem_id].add(elem)
            else:
                self.xml_ids[elem_id] = {elem}


if __name__ == "__main__":
    raise SystemExit(StatefulXmlLinter.main())

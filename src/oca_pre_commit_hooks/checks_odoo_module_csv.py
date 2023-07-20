import csv
import os
from collections import defaultdict
from typing import Sequence, Set, Union

from oca_pre_commit_hooks import utils
from oca_pre_commit_hooks.base_checker import BaseChecker


class ChecksOdooModuleCSV(BaseChecker):
    def __init__(
        self,
        manifest_datas: Union[Sequence, None] = None,
        module_name: str = None,
        enable: Union[Set, None] = None,
        disable: Union[Set, None] = None,
    ):
        super().__init__(enable, disable, module_name)

        self.manifest_datas = manifest_datas or []
        for manifest_data in manifest_datas:
            manifest_data.update(
                {
                    "model": os.path.splitext(os.path.basename(manifest_data["filename"]))[0],
                }
            )

    @utils.only_required_for_checks("csv-syntax-error", "csv-duplicate-record-id")
    def check_csv(self):
        """* Check csv-duplicate-record-id
        duplicate CSV "id" AKA xmlid but for CSV files

        * Check csv-syntax-error
        Check syntax error for CSV files declared in the manifest
        """
        csvids = defaultdict(list)
        for manifest_data in self.manifest_datas:
            try:
                with open(manifest_data["filename"], encoding="UTF-8") as f_csv:
                    csv_r = csv.DictReader(f_csv)
                    if not csv_r or "id" not in csv_r.fieldnames:
                        continue
                    for record in csv_r:
                        record_id = record["id"]
                        csvid = f"{manifest_data['data_section']}/{record_id}"
                        csvids[csvid].append(
                            (
                                manifest_data["filename_short"],
                                csv_r.line_num,
                                manifest_data["model"],
                            )
                        )
            except (FileNotFoundError, csv.Error, UnicodeDecodeError) as csv_err:
                if self.is_message_enabled("csv-syntax-error"):
                    self.checks_errors["csv-syntax-error"].append(f'{manifest_data["filename_short"]}:1 {csv_err}')

        if self.is_message_enabled("csv-duplicate-record-id"):
            for csvid, records in csvids.items():
                if len(records) < 2:
                    continue
                self.checks_errors["csv-duplicate-record-id"].append(
                    f"{records[0][0]}:{records[0][1]} "
                    f'Duplicate CSV record id "{csvid}" in '
                    f'{", ".join(f"{record[0]}:{record[1]}" for record in records[1:])}'
                )

import csv
import os
from collections import defaultdict


class ChecksOdooModuleCSV:
    def __init__(self, manifest_datas, module_name):
        self.module_name = module_name
        self.manifest_datas = manifest_datas
        for manifest_data in manifest_datas:
            manifest_data.update(
                {
                    "model": os.path.splitext(os.path.basename(manifest_data["filename"]))[0],
                }
            )
        self.checks_errors = defaultdict(list)

    def check_csv(self):
        """*Check csv_duplicate_record_id
        duplicate CSV "id" AKA xmlid but for CSV files
        """
        csvids = defaultdict(list)
        for manifest_data in self.manifest_datas:
            try:
                with open(manifest_data["filename"], "r", encoding="UTF-8") as f_csv:
                    csv_r = csv.DictReader(f_csv)
                    if not csv_r or "id" not in csv_r.fieldnames:
                        continue
                    for record in csv_r:
                        record_id = record["id"]
                        csvid = f"{manifest_data['data_section']}/{record_id}"
                        csvids[csvid].append(
                            (
                                manifest_data["filename"],
                                csv_r.line_num,
                                manifest_data["model"],
                            )
                        )
            except (FileNotFoundError, csv.Error) as csv_err:  # pragma: no cover
                self.checks_errors["csv_syntax_error"].append(f'{manifest_data["filename"]} {csv_err}')
        for csvid, records in csvids.items():
            if len(records) < 2:
                continue
            self.checks_errors["csv_duplicate_record_id"].append(
                f"{records[0][0]}:{records[0][1]} "
                f'Duplicate CSV record id "{csvid}" in '
                f'{", ".join(f"{record[0]}:{record[1]}" for record in records[1:])}'
            )

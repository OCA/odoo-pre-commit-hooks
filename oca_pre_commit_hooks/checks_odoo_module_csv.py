import os
import csv
from collections import defaultdict


class ChecksOdooModuleCSV:
    def __init__(self, manifest_csvs, module_name):
        self.module_name = module_name
        self.manifest_csvs = manifest_csvs
        for manifest_csv in manifest_csvs:
            manifest_csv.update({
                "model": os.path.splitext(os.path.basename(manifest_csv["filename"]))[0],
            })
        self.checks_errors = defaultdict(list)

    def check_csv_duplicate_id(self):
        """Check duplicate CSV "id" AKA xmlid but for CSV files
        """
        csvids = defaultdict(list)
        for manifest_csv in self.manifest_csvs:
            try:
                with open(manifest_csv["filename"], "r") as f_csv:
                    csv_r = csv.DictReader(f_csv)
                    if not csv_r or "id" not in csv_r.fieldnames:
                        continue
                    for record in csv_r:
                        record_id = record["id"]
                        csvid = f"{manifest_csv['data_section']}/{record_id}"
                        csvids[csvid].append((manifest_csv["filename"], csv_r.line_num, manifest_csv["model"]))
            except (FileNotFoundError, csv.Error) as csv_err:
                # csv syntax error is raised from another hook
                continue
        for csvid, records in csvids.items():
            if len(records) < 2:
                continue
            self.checks_errors["csv_duplicate_record_id"].append(
                f'{records[0][0]}:{records[0][1]} '
                f'Duplicate CSV record id "{csvid}" in '
                f'{", ".join(f"{record[0]}:{record[1]}" for record in records[1:])}'
            )

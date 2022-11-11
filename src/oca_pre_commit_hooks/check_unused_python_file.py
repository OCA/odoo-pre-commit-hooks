import argparse
import ast
import functools
import os
from typing import List, Set, Union


@functools.lru_cache()
def get_imported_files(dirname: str) -> Set[str]:
    imported_files = set()
    init_file = os.path.join(dirname, "__init__.py")
    if os.path.exists(init_file):
        with open(init_file, encoding="utf-8") as init_fd:
            init_ast = ast.parse(init_fd.read())

        if isinstance(init_ast.body, list):
            for module in filter(lambda elem: isinstance(elem, ast.ImportFrom), init_ast.body):
                for name in module.names:
                    imported_files.add(name.name)

    return imported_files


def check_unused_python_file(filenames: List[str]) -> int:
    status = 0
    for filename in filenames:
        if os.path.basename(filename)[:-3] not in get_imported_files(os.path.dirname(filename)):
            print(f"{filename}: not imported")
            status = -1

    return status


def main(argv: Union[List[str], None] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*")
    args = parser.parse_args(argv)

    return check_unused_python_file(args.filenames)

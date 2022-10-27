import argparse
import configparser
from os import getcwd
from os.path import exists, join

from oca_pre_commit_hooks.utils import top_path

CONFIG_NAME = ".oca_hooks.cfg"
MSG_CTRL = "MESSAGES_CONTROL"


def parse_disable(value):
    return set(value.split(","))


class GlobalParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()
        self.add_argument(
            "--no-verbose",
            action="store_true",
            default=False,
            help="If enabled so disable verbose mode.",
        )
        self.add_argument(
            "--no-exit",
            action="store_true",
            default=False,
            help="If enabled so it will not call exit.",
        )
        self.add_argument(
            "--disable",
            "-d",
            type=parse_disable,
            default=set(),
            help="Disable the checker with the given 'check-name', separated by commas.",
        )
        self.add_argument(
            "--enable",
            "-e",
            type=parse_disable,
            default=set(),
            help=(
                "Enable the checker with the given 'check-name', separated by commas. "
                "Default: All checks are enabled by default"
            ),
        )
        self.add_argument("--config", "-c", type=argparse.FileType("r"), help="Path to a configuration file")

    def parse_args(self, args=None, namespace=None):
        res = super().parse_args(args)

        # --enable, --disable takes precedence over config file so no point parsing it.
        if res.enable and res.disable:
            return res

        if not res.config and exists(join(getcwd(), CONFIG_NAME)):
            res.config = join(getcwd(), CONFIG_NAME)
        elif exists(join(top_path(getcwd()), CONFIG_NAME)):
            res.config = join(top_path(getcwd()), CONFIG_NAME)

        if res.config:
            conf = configparser.ConfigParser()
            conf.read_file(res.config)

            if conf.has_section(MSG_CTRL):
                message_conf = conf[MSG_CTRL]
                if not res.enable and message_conf.get("enable", None):
                    res.enable = parse_disable(message_conf.get("enable"))
                if not res.disable and message_conf.get("disable", None):
                    res.disable = parse_disable(message_conf.get("disable"))

            res.config.close()

        # Not expected/used by any other program component as of now.
        delattr(res, "config")
        return res

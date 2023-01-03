from dataclasses import dataclass
from typing import Mapping, Set


@dataclass()
class SchedulerConfiguration:
    filenames: Set[str]  # Files to run the checker on.
    enable: Set[str]  # All enabled messages.
    disable: Set[str]  # All disabled messages.
    list_msgs: bool = False  # Do not run any checks. Just print out the messages this linter emits.
    zero_exit: bool = False  # If true the linter will always produce 0 as a return code.
    kwargs: Mapping = None  # Extra arguments which can be used for customization. Implementation dependent.

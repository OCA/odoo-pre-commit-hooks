from dataclasses import dataclass


@dataclass
class Message:
    key: str  # Contains the message-id, for example xml-duplicate-record-id
    file: str  # Absolute path to the file which committed the violation
    args: tuple = tuple()  # Extra arguments used by the Printer to format the message
    # The following values won't be shown to the user if they are negative.
    line: int = -1  # Optional. Line in the file where the violation was found.
    column: int = -1  # Optional. Column where the violation happened.

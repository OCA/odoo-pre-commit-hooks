class NodeContent:
    """Represents the content and metadata of an XML node."""

    def __init__(self, filename, node):
        """Initialize by reading and parsing the node from the file.

        Args:
            filename: Path to the XML file
            node: lxml node element to extract
        """
        self.filename = filename
        self.node = node

        # Initialize attributes
        self.content_before = b""
        self.content_node = b""
        self.content_after = b""
        self.node_comment = b""
        self.start_sourceline = None
        self.end_sourceline = None

        # Read and parse the node
        self._read_node()

    def _read_node(self):  # noqa:C901 pylint:disable=too-complex
        """Internal method to read the content of the file and extract node information."""
        # TODO: Get the sourceline of a particular attribute
        # Determine the search start line
        if (node_previous := self.node.getprevious()) is not None:
            search_start_line = node_previous.sourceline + 1
        elif (node_parent := self.node.getparent()) is not None:
            search_start_line = node_parent.sourceline + 1
        else:
            search_start_line = 2  # first element and it is the root

        search_end_line = self.node.sourceline
        node_tag = self.node.tag.encode() if isinstance(self.node.tag, str) else self.node.tag

        # Read all lines from file
        with open(self.filename, "rb") as f_content:
            all_lines = list((i, line) for i, line in enumerate(f_content, start=1))

        # Find the actual node start by looking for the tag
        node_start_idx = None
        for idx, (no_line, line) in enumerate(all_lines):
            if search_start_line <= no_line <= search_end_line:
                stripped_line = line.lstrip()
                if stripped_line.startswith(b"<" + node_tag):
                    node_start_idx = idx
                    self.start_sourceline = no_line
                    break

        if node_start_idx is None:
            # Fallback: use search_end_line
            self.start_sourceline = search_end_line
            for idx, (no_line, _line) in enumerate(all_lines):
                if no_line == search_end_line:
                    node_start_idx = idx
                    break

        # Find the actual node end
        node_end_idx = node_start_idx
        self.end_sourceline = self.start_sourceline

        for idx in range(node_start_idx, len(all_lines)):
            no_line, line = all_lines[idx]
            stripped_line = line.lstrip()

            if idx == node_start_idx:
                # Check if self-closing or single-line
                if b"/>" in line:
                    node_end_idx = idx
                    self.end_sourceline = no_line
                    break
                if b"<" + node_tag in line and b"</" + node_tag in line:
                    node_end_idx = idx
                    self.end_sourceline = no_line
                    break
            else:
                # Look for closing tag
                if b"</" + node_tag + b">" in line or b"</" + node_tag + b" " in line:
                    node_end_idx = idx
                    self.end_sourceline = no_line
                    break
                if b"/>" in stripped_line and not stripped_line.startswith(b"<"):
                    # Self-closing continuation
                    node_end_idx = idx
                    self.end_sourceline = no_line
                    break

        # Look backwards from node start for comment
        for idx in range(node_start_idx - 1, -1, -1):
            no_line, line = all_lines[idx]
            stripped_line = line.lstrip()

            # Skip empty lines
            if stripped_line in (b"", b"\n", b"\r\n"):
                continue

            # Check if it's a comment end
            if b"-->" in stripped_line:
                # Found comment end, now find comment start
                comment_lines = []
                for comment_idx in range(idx, -1, -1):
                    _comment_no_line, comment_line = all_lines[comment_idx]
                    comment_lines.insert(0, comment_line)
                    if b"<!--" in comment_line:
                        self.node_comment = b"".join(comment_lines)
                        break
            break

        # Build content_before, content_node, content_after
        for idx, (_no_line, line) in enumerate(all_lines):
            if idx < node_start_idx:
                # Skip comment lines if they were captured
                if self.node_comment and line in self.node_comment:
                    self.content_before += line
                    continue
                self.content_before += line
            elif node_start_idx <= idx <= node_end_idx:
                self.content_node += line
            else:
                self.content_after += line

        # Remove comment from content_before if present
        if self.node_comment:
            # Find and remove the exact comment sequence
            comment_start = self.content_before.rfind(self.node_comment)
            if comment_start != -1:
                self.content_before = (
                    self.content_before[:comment_start] + self.content_before[comment_start + len(self.node_comment) :]
                )

    def __str__(self):
        """Return the complete content in order."""
        return (self.content_before + self.node_comment + self.content_node + self.content_after).decode(
            "utf-8", errors="replace"
        )

    def __bytes__(self):
        """Return the complete content as bytes."""
        return self.content_before + self.node_comment + self.content_node + self.content_after

    def __repr__(self):
        return (
            f"NodeContent(start_line={self.start_sourceline}, "
            f"end_line={self.end_sourceline}, "
            f"has_comment={len(self.node_comment) > 0})"
        )

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
        # Determine the search start line
        if (node_previous := self.node.getprevious()) is not None:
            search_start_line = node_previous.sourceline + 1
        elif (node_parent := self.node.getparent()) is not None:
            # Start from parent line (not +1) because child tags can be on same line as parent
            search_start_line = node_parent.sourceline
        else:
            search_start_line = 2  # first element and it is the root

        search_end_line = self.node.sourceline
        node_tag = self.node.tag.encode() if isinstance(self.node.tag, str) else self.node.tag

        # Read all lines from file
        with open(self.filename, "rb") as f_content:
            all_lines = list((i, line) for i, line in enumerate(f_content, start=1))

        # Find the actual node start by looking for the tag
        node_start_idx = None
        node_start_col = 0  # Column position within the line
        
        # When there are multiple tags on the same line, we need to find the RIGHT one
        # We'll collect all candidates and use additional heuristics
        candidates = []
        
        for idx, (no_line, line) in enumerate(all_lines):
            if search_start_line <= no_line <= search_end_line:
                # Look for the tag anywhere in the line, not just at the start
                tag_pattern = b"<" + node_tag
                tag_pos = 0
                
                # Find ALL occurrences of the tag in this line
                while True:
                    tag_pos = line.find(tag_pattern, tag_pos)
                    if tag_pos == -1:
                        break
                    
                    # Verify it's actually a tag start (followed by space, >, or /)
                    check_pos = tag_pos + len(tag_pattern)
                    is_valid = False
                    
                    if check_pos >= len(line):
                        # Tag at end of line is valid
                        is_valid = True
                    else:
                        next_char = line[check_pos:check_pos+1]
                        # Valid tag if followed by space, >, /, or newline
                        if next_char in (b" ", b">", b"/", b"\n", b"\r"):
                            is_valid = True
                    
                    if is_valid:
                        candidates.append({
                            'idx': idx,
                            'line_no': no_line,
                            'col': tag_pos,
                            'line': line
                        })
                    
                    tag_pos += 1
        
        # Choose the best candidate
        if candidates:
            # If we only have one candidate, use it
            if len(candidates) == 1:
                best = candidates[0]
                node_start_idx = best['idx']
                node_start_col = best['col']
                self.start_sourceline = best['line_no']
            else:
                # Multiple candidates - need to find the right one
                # Strategy: use node attributes to identify the correct tag
                best = None
                
                # Get the first attribute of the node if it exists
                node_attrib_key = None
                node_attrib_value = None
                if self.node.attrib:
                    node_attrib_key = list(self.node.attrib.keys())[0]
                    node_attrib_value = self.node.attrib[node_attrib_key]
                
                # Try to match by attribute
                if node_attrib_key:
                    attr_pattern = f'{node_attrib_key}='.encode()
                    for candidate in candidates:
                        # Look in the line and following lines for this attribute
                        idx = candidate['idx']
                        # Check current line from the tag position
                        search_text = candidate['line'][candidate['col']:]
                        # Also check next few lines (in case attributes span lines)
                        for i in range(idx, min(idx + 5, len(all_lines))):
                            if i > idx:
                                search_text += all_lines[i][1]
                        
                        if attr_pattern in search_text:
                            best = candidate
                            break
                
                # If we didn't find by attribute, use line number heuristic
                if best is None:
                    # Prefer candidates on the target line (node.sourceline)
                    candidates_on_target_line = [c for c in candidates if c['line_no'] == search_end_line]
                    
                    if candidates_on_target_line:
                        # If multiple on target line, prefer the last one
                        best = candidates_on_target_line[-1]
                    else:
                        # Use the last candidate overall
                        best = candidates[-1]
                
                node_start_idx = best['idx']
                node_start_col = best['col']
                self.start_sourceline = best['line_no']

        if node_start_idx is None:
            # Fallback: use search_end_line
            self.start_sourceline = search_end_line
            for idx, (no_line, _line) in enumerate(all_lines):
                if no_line == search_end_line:
                    node_start_idx = idx
                    break

        # Find the actual node end
        node_end_idx = node_start_idx
        node_end_col = None  # Column position where node ends
        self.end_sourceline = self.start_sourceline
        
        # Track nesting level to handle cases where parent and child have same tag
        nesting_level = 0

        for idx in range(node_start_idx, len(all_lines)):
            no_line, line = all_lines[idx]

            if idx == node_start_idx:
                # For the starting line, only look at content from node_start_col onwards
                relevant_line = line[node_start_col:]
                
                # Check if self-closing on same line
                self_close_pos = relevant_line.find(b"/>")
                if self_close_pos != -1:
                    # Verify this is the closing for our tag, not a nested one
                    # Simple check: see if there's another opening tag between start and close
                    between = relevant_line[:self_close_pos]
                    # Count opening tags in between
                    temp_count = between.count(b"<" + node_tag)
                    if temp_count == 1:  # Only our opening tag
                        node_end_idx = idx
                        node_end_col = node_start_col + self_close_pos + 2
                        self.end_sourceline = no_line
                        break
                
                # Check if opening and closing tag on same line
                close_tag = b"</" + node_tag + b">"
                close_pos = relevant_line.find(close_tag)
                if close_pos != -1:
                    node_end_idx = idx
                    node_end_col = node_start_col + close_pos + len(close_tag)
                    self.end_sourceline = no_line
                    break
                
                # Node continues beyond this line
                nesting_level = 1
            else:
                # Look for closing patterns
                stripped_line = line.lstrip()
                
                # Check for self-closing continuation (when tag opened in previous line)
                # This handles cases like:
                # <span
                #    attr="value"
                # />
                if b"/>" in line:
                    # Check if this is a standalone /> (not part of a new tag)
                    # by seeing if the line starts with /> or has /> after attributes
                    if stripped_line.startswith(b"/>") or (b">" not in line[:line.find(b"/>")] if b"/>" in line else False):
                        node_end_idx = idx
                        node_end_col = line.find(b"/>") + 2
                        self.end_sourceline = no_line
                        nesting_level -= 1
                        if nesting_level == 0:
                            break
                
                # Look for closing tag
                close_tag = b"</" + node_tag + b">"
                if close_tag in line:
                    node_end_idx = idx
                    node_end_col = line.find(close_tag) + len(close_tag)
                    self.end_sourceline = no_line
                    nesting_level -= 1
                    if nesting_level == 0:
                        break
                
                # Count any new opening tags to track nesting
                pos = 0
                while True:
                    pos = line.find(b"<" + node_tag, pos)
                    if pos == -1:
                        break
                    # Verify it's a real opening tag
                    check_pos = pos + len(node_tag) + 1
                    if check_pos < len(line):
                        next_char = line[check_pos:check_pos+1]
                        if next_char in (b" ", b">", b"/", b"\n", b"\r"):
                            nesting_level += 1
                    pos += 1

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
            elif idx == node_start_idx:
                # For the start line, split at the column position
                self.content_before += line[:node_start_col]
                
                if idx == node_end_idx:
                    # Node starts and ends on same line
                    self.content_node += line[node_start_col:node_end_col]
                    self.content_after += line[node_end_col:]
                else:
                    # Node continues to next line(s)
                    self.content_node += line[node_start_col:]
            elif node_start_idx < idx < node_end_idx:
                # Full lines that are part of the node
                self.content_node += line
            elif idx == node_end_idx and idx != node_start_idx:
                # Last line of the node
                self.content_node += line[:node_end_col]
                self.content_after += line[node_end_col:]
            elif idx > node_end_idx:
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

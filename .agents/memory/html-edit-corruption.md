---
name: HTML file edit corruption pattern
description: Editing strings containing single quotes inside JS template literals in index.html causes file corruption — the Edit tool mismatches quote boundaries and splits content across the file end.
---

# HTML Edit Corruption Risk

**Rule:** When editing any JS line in `backend/app/static/index.html` that contains a string with a single quote (`'`) where the old_string and new_string differ only in the string content (e.g., changing `:'—'` to `:'$'+...`), the Edit tool can silently corrupt the file by splitting the line mid-expression and appending the tail after `</html>`.

**Why:** The Edit tool performs byte-level matching. When the old_string contains a single quote that also appears as a JS string delimiter, ambiguous matching can cause the replacement to span across content, splitting the file.

**How to apply:**
- For any edit to a JS line that changes string literals containing `'`, use a Python script (`python3 -c "..."`) to do the replacement safely instead of the Edit tool.
- Example safe pattern:
  ```python
  with open(path, 'r') as f: lines = f.readlines()
  lines[N] = "replacement line\n"
  with open(path, 'w') as f: f.writelines(lines)
  ```
- After any Edit to the HTML file, always verify `wc -l` hasn't grown unexpectedly and check for orphaned content after `</html>` via `grep -n '</html>' file`.
- If corruption occurs: truncate at first `</html>` using `python3` (not `head -N` alone — verify the line number).

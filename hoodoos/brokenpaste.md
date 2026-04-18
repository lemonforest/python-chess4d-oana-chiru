Stop. Three items from previous prompts are still not done. Do NOT run
any verification until every change is made. Do NOT write any new code.
Do NOT start Deliverable 2.

Execute these exact commands and edits, in order. Report each line
completed or failed.

## 1. Delete parity.py

```
rm src/chess4d/parity.py
```

Then: `ls src/chess4d/` and paste the actual output.
Expected: only `__init__.py`, `board.py`, `types.py`.

## 2. Replace LICENSE file contents

Replace the ENTIRE contents of `LICENSE` with this exact text
(copy-paste verbatim, no additions, no header, no modifications):

```
This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org/>
```

Then: `wc -c LICENSE` and paste the actual output.
Expected: approximately 1200-1300 bytes, not ~35000.

## 3. Fix pyproject.toml

In `pyproject.toml`, change the line:

```
license = { text = "GPL-3.0-or-later" }
```

to exactly:

```
license = { text = "Unlicense" }
```

Then: `grep "license" pyproject.toml` and paste the actual output.

## 4. Fix README.md

In `README.md`, change the License section. Replace:

```
## License

GPL-3.0-or-later. See `LICENSE`.
```

with exactly:

```
## License

Unlicense (public domain). See `LICENSE`.
```

Then: `grep -A1 "^## License" README.md` and paste the actual output.

## 5. Fix CLAUDE.md

In `CLAUDE.md`, change the bullet:

```
- `LICENSE` — GPL-3.0
```

to exactly:

```
- `LICENSE` — Unlicense
```

Then: `grep "LICENSE" CLAUDE.md` and paste the actual output.

## 6. Sweep for stragglers

Run `grep -ri "GPL" . --include="*.py" --include="*.toml" --include="*.md"`
and paste the actual output.
Expected: empty.

## Reporting

For each of 1–6, paste the actual shell output verbatim. If a command
truncates in display, re-run it and paste again. I will not accept
"commands were truncated" as a status — the work either happened in the
filesystem or it didn't, and the filesystem is queryable regardless of
terminal display.

Do not proceed past step 6. Do not start Deliverable 2.
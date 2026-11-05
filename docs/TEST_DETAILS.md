# pyrtma — Test catalogue

**Claude:** read `docs/WORKFLOW.md` first, then `docs/PROGRESS.md`, and follow the stage its **Next** line names.

Run with `pytest -v`. `tests/test_docs.py` checks that this file lists every test function, and nothing else.

The layout:

- One `##` heading per test file: `## test_<module>.py — <what it covers> (needs: <markers or tools, or none>)`.
- Optionally, a paragraph on setup that the file's tests share.
- A table for the test functions outside classes, right under the file's heading, then a `###` heading for each test class, named as in the code, with its own table.
- One row per test function: `| Test | Purpose | Approach |`. Purpose says what behavior the test pins down; Approach says how, such as the input or the stand-in it uses. Parametrized cases share their function's row.

## test_docs.py — this catalogue (needs: none)

| Test | Purpose | Approach |
|---|---|---|
| `test_every_test_is_catalogued` | This file lists every test function in `tests/`, and has no entries for tests that no longer exist. | Compares the names found by `ast` with the names in the tables here. |
| `test_catalogue_names_follow_headings` | A row is named by its file heading, plus its class heading when it has one; other sections and other tables are ignored. | A small catalogue with a module-level row, a class row, and an unrelated table. |
| `test_collected_tests_include_class_methods` | Test functions are found at module level and inside `Test` classes, and nowhere else. | A test file in `tmp_path` with a helper, a test, a test class, and a non-test class. |

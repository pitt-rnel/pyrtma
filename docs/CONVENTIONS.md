# Conventions

## Language and tooling

- Target Python 3.10; the library must keep running on it. `X | None` and `match` are fine. Avoid what needs a later version, such as `type` alias statements (3.12), `typing.Self`, `ExceptionGroup` and `except*`, and `tomllib` (3.11). Moving to 3.13 is a later decision.
- Type annotations on every new or changed function, method, and module-level constant. Pyright runs in basic mode on `src/` and `tests/`, because the ctypes and descriptor code would not pass strict mode.
- Format with Black (default settings, 88 columns).
- Files use LF line endings, including in patches. Tests that need CRLF write it explicitly as bytes.
- Use comments to explain complex code areas.
- Google-style docstrings on all public modules, classes, and functions. Include `Args`, `Returns`, `Raises`, and `Yields` sections where they apply. Test functions don't need docstrings.

## Design rules

These design rules, and the annotation and docstring rules above, apply to code written or changed from now on. Existing code is not retrofitted to follow them. Formatting and line endings apply to the whole repo.

- **Output stays at the edges.** Only the entry point and its command handlers print. Other modules return values or raise exceptions.
- **Subprocess calls use argument lists**, never `shell=True`.
- **Use `pathlib.Path`** for all filesystem paths. Read and write text with an explicit `encoding="utf-8"`.
- **Injectable defaults.** Functions that read the environment, home directory, platform, or clock accept them as optional parameters so tests can supply them.

## Project rules

- **The wire format is frozen.** No change to the message header, message layouts, type hash values, or core message and module IDs. `tests/test_wire_format.py` enforces this; never edit its snapshot to make a change pass. The one exception was Phase 9, which changed by decision how type hashes are computed, so that each covers its definition as written and as resolved; the snapshots' hash values were regenerated then, and nothing else in them.
- **The public API stays compatible.** Don't remove or rename public names or parameters. New parameters are keyword-only and default to the current behavior, unless that behavior is the bug being fixed.
- **Behavior changes go in `docs/CHANGELOG.md`** under "Unreleased", in the same patch as the change.
- **Long-running loops isolate failures.** In the manager, data logger, and web manager, an exception caused by one client or one dataset is logged, the offender is dropped, and the loop continues.
- **Errors callers handle are the package's own.** Public client methods raise exceptions from `pyrtma.exceptions`, not raw `OSError`.
- **Logging, not printing.** Library code reports through its logger. Only command-line entry points print.
- **Fixes start with a failing test.** Write the regression test first and confirm it fails on the current code. Its `TEST_DETAILS.md` Purpose starts with the finding ID from `CODE_REVIEW.md`, such as "C2:", or with the finding's heading for Medium and Low findings, such as "Manager routing:".

## Tests

- pytest, with tests in `tests/` named `test_<module>.py`. The existing `unittest` suites run under pytest and are not rewritten.
- Tests that need a manager or clients use the fixtures in `tests/conftest.py`. New tests use no fixed or random port numbers and no fixed sleeps; they wait on a condition with a deadline.
- Mark tests that start a manager or open sockets `integration`, and tests that need `gcc` or `node` `toolchain`.
- Shared fixtures live in `tests/conftest.py`. Tests never touch the user's real folders or settings.
- Arrange, act, assert, with a blank line between sections when a test has more than a couple of lines.
- Every test is listed in `TEST_DETAILS.md`. `tests/test_docs.py` fails when a test is missing from it or an entry no longer matches a test.

## Checks before handing off

```
black --check .
pyright
pytest
```

CI regenerates `tests/test_msg_defs/test_defs.py` with `python -m pyrtma.compile` before running pytest; run the same step locally after changing the compiler.

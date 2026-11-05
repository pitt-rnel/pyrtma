# Conventions

**Claude:** read `docs/WORKFLOW.md` first, then `docs/PROGRESS.md`, and follow the stage its **Next** line names.

## Language and tooling

- Target Python 3.13. Modern syntax is welcome: `X | None`, `type` aliases, `match`.
- Type annotations on every function, method, and module-level constant. Pyright runs in strict mode on `src/` and `tests/`.
- Format with Black (default settings, 88 columns).
- Files use LF line endings, including in patches. Tests that need CRLF write it explicitly as bytes.
- Google-style docstrings on all public modules, classes, and functions. Include `Args`, `Returns`, `Raises`, and `Yields` sections where they apply. Test functions don't need docstrings.

## Design rules

- **Output stays at the edges.** Only the entry point and its command handlers print. Other modules return values or raise exceptions.
- **Subprocess calls use argument lists**, never `shell=True`.
- **Use `pathlib.Path`** for all filesystem paths. Read and write text with an explicit `encoding="utf-8"`.
- **Injectable defaults.** Functions that read the environment, home directory, platform, or clock accept them as optional parameters so tests can supply them.

## Project rules

*Plan: rules particular to pyrtma, added as the design settles.*

## Tests

- pytest, with tests in `tests/` named `test_<module>.py`.
- Shared fixtures live in `tests/conftest.py`. Tests never touch the user's real folders or settings.
- Arrange, act, assert, with a blank line between sections when a test has more than a couple of lines.
- Every test is listed in `TEST_DETAILS.md`. `tests/test_docs.py` fails when a test is missing from it or an entry no longer matches a test.

## Checks before handing off

```
black --check .
pyright
pytest
```

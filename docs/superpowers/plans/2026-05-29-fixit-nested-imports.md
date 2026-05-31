# Fixit Nested Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up Fixit and enforce a custom rule that rejects nested Python imports except imports under `if TYPE_CHECKING:`.

**Architecture:** Add one local Fixit rule package, configure Fixit to load that rule, and wire Fixit into the existing lint and pre-commit workflows. Run the rule across all Python files and move current nested imports to module scope or a `TYPE_CHECKING` block.

**Tech Stack:** Python, Fixit, LibCST, uv, tox, pre-commit, Ruff.

---

## File Structure

- Create `lint_rules/__init__.py`: makes the local Fixit rules directory importable.
- Create `lint_rules/no_nested_imports.py`: contains the custom `NoNestedImportsRule` and embedded Fixit valid/invalid examples.
- Create `.fixit.toml`: marks this repo as the Fixit config root and enables the local rule.
- Modify `pyproject.toml`: adds Fixit to the `dev` dependency group.
- Modify `tox.ini`: installs Fixit in the lint environment and runs `fixit lint .`.
- Modify `.pre-commit-config.yaml`: adds a local Fixit hook.
- Modify any Python files reported by the new rule: move disallowed imports to the top of the file or under `if TYPE_CHECKING:`.

### Task 1: Add The Custom Rule

**Files:**
- Create: `lint_rules/__init__.py`
- Create: `lint_rules/no_nested_imports.py`

- [ ] **Step 1: Create the local rules package**

Create `lint_rules/__init__.py` as an empty file.

- [ ] **Step 2: Write embedded Fixit examples first**

Create `lint_rules/no_nested_imports.py` with this initial test-focused rule shell:

```python
from fixit import Invalid, LintRule, Valid
import libcst as cst


class NoNestedImportsRule(LintRule):
    MESSAGE = "Imports must be at module scope or under if TYPE_CHECKING."

    VALID = [
        Valid("import os\nfrom pathlib import Path\n"),
        Valid(
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n"
            "    from example import Thing\n"
        ),
    ]

    INVALID = [
        Invalid(
            "def run():\n"
            "    import os\n"
        ),
        Invalid(
            "if enabled:\n"
            "    from example import Thing\n"
        ),
    ]

    def visit_Import(self, node: cst.Import) -> None:
        return None

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        return None
```

- [ ] **Step 3: Run examples and verify they fail**

Run: `uv run fixit test lint_rules.no_nested_imports`

Expected: failure because the invalid examples are not reported yet.

- [ ] **Step 4: Implement minimal rule logic**

Replace `lint_rules/no_nested_imports.py` with:

```python
from fixit import Invalid, LintRule, Valid
import libcst as cst
from libcst.metadata import ParentNodeProvider


class NoNestedImportsRule(LintRule):
    MESSAGE = "Imports must be at module scope or under if TYPE_CHECKING."
    METADATA_DEPENDENCIES = (ParentNodeProvider,)

    VALID = [
        Valid("import os\nfrom pathlib import Path\n"),
        Valid(
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n"
            "    from example import Thing\n"
        ),
    ]

    INVALID = [
        Invalid(
            "def run():\n"
            "    import os\n"
        ),
        Invalid(
            "if enabled:\n"
            "    from example import Thing\n"
        ),
    ]

    def visit_Import(self, node: cst.Import) -> None:
        self._check_import(node)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self._check_import(node)

    def _check_import(self, node: cst.Import | cst.ImportFrom) -> None:
        statement = self.get_metadata(ParentNodeProvider, node)
        parent = self.get_metadata(ParentNodeProvider, statement)

        if isinstance(parent, cst.Module):
            return

        if self._is_under_type_checking(node):
            return

        self.report(node)

    def _is_under_type_checking(self, node: cst.CSTNode) -> bool:
        current = node
        while not isinstance(current, cst.Module):
            parent = self.get_metadata(ParentNodeProvider, current)
            if isinstance(parent, cst.If) and self._is_type_checking_test(parent.test):
                return True
            current = parent
        return False

    def _is_type_checking_test(self, test: cst.BaseExpression) -> bool:
        return isinstance(test, cst.Name) and test.value == "TYPE_CHECKING"
```

- [ ] **Step 5: Run examples and verify they pass**

Run: `uv run fixit test lint_rules.no_nested_imports`

Expected: all valid and invalid examples pass.

### Task 2: Configure Fixit

**Files:**
- Create: `.fixit.toml`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add repository Fixit config**

Create `.fixit.toml`:

```toml
[tool.fixit]
root = true
enable = [
    ".lint_rules.no_nested_imports:NoNestedImportsRule",
]
```

- [ ] **Step 2: Add Fixit to dev dependencies**

In `pyproject.toml`, add `fixit` to `[dependency-groups].dev`:

```toml
dev = [
    "ruff==0.12.9",
    "pre-commit>=4.0.0",
    "ipdb>=0.13.13",
    "tox>=4.11.0",
    "pyright>=1.1.400",
    "django-types>=0.19.1",
    "wagtail>=7.1",
    "zensical>=0.0.43",
    "fixit",
]
```

- [ ] **Step 3: Sync lockfile**

Run: `uv lock`

Expected: `uv.lock` updates to include Fixit and its dependencies.

- [ ] **Step 4: Verify Fixit can load the config**

Run: `uv run fixit test .lint_rules.no_nested_imports`

Expected: the custom rule examples pass.

### Task 3: Wire Fixit Into Existing Checks

**Files:**
- Modify: `tox.ini`
- Modify: `.pre-commit-config.yaml`

- [ ] **Step 1: Add Fixit to tox lint deps and commands**

Update `[testenv:lint]` in `tox.ini` to:

```ini
[testenv:lint]
deps =
    ruff==0.12.9
    fixit
commands =
    ruff check .
    ruff format --check .
    fixit lint .
```

- [ ] **Step 2: Add local pre-commit hook**

Append this repo entry to `.pre-commit-config.yaml`:

```yaml
  - repo: local
    hooks:
      - id: fixit
        name: fixit
        entry: fixit lint .
        language: system
        pass_filenames: false
        types: [python]
```

- [ ] **Step 3: Verify pre-commit config parses**

Run: `uv run pre-commit validate-config`

Expected: command exits successfully with no output.

### Task 4: Clean Up Existing Nested Imports

**Files:**
- Modify: any `.py` files reported by `uv run fixit lint .`

- [ ] **Step 1: Run Fixit against the whole repo**

Run: `uv run fixit lint .`

Expected: Fixit reports every current nested import violation.

- [ ] **Step 2: Move runtime nested imports to module scope**

For each reported runtime import, move the import to the top import block of that file. For example, if `tests/test_loaders.py` contains this inside a test:

```python
def test_document_loader():
    from wagtail.documents.models import Document
```

Change it to:

```python
from wagtail.documents.models import Document


def test_document_loader():
    ...
```

- [ ] **Step 3: Move type-only nested imports under TYPE_CHECKING**

If a reported import is used only for annotations, add `TYPE_CHECKING` to the file's typing imports and place the type-only import under a module-level guard:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from example import Thing
```

- [ ] **Step 4: Re-run Fixit**

Run: `uv run fixit lint .`

Expected: no `NoNestedImportsRule` violations remain.

### Task 5: Final Verification

**Files:**
- No additional files expected.

- [ ] **Step 1: Run the custom rule examples**

Run: `uv run fixit test .lint_rules.no_nested_imports`

Expected: all examples pass.

- [ ] **Step 2: Run full lint**

Run: `uv run tox -e lint`

Expected: Ruff check, Ruff format check, and Fixit lint all pass.

- [ ] **Step 3: Check whitespace in the diff**

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 4: Review changed files**

Run: `git diff --stat`

Expected: changes are limited to Fixit setup, the local rule, lockfile updates, and import cleanup.

## Self-Review

- Spec coverage: The plan installs Fixit, adds one custom nested-import rule, allows module-level and `TYPE_CHECKING` imports, applies the rule to all Python files, and wires it into lint/pre-commit.
- Placeholder scan: No placeholders remain; each task has exact files, commands, and expected results.
- Type consistency: The rule class name is consistently `NoNestedImportsRule`, and the config references the same class.

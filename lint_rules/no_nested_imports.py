import libcst as cst
from fixit import Invalid, LintRule, Valid
from libcst.metadata import ParentNodeProvider


class NoNestedImportsRule(LintRule):
    """Require imports to stay at module level or inside TYPE_CHECKING blocks."""

    MESSAGE = "Imports must be at module level or inside if TYPE_CHECKING blocks."
    METADATA_DEPENDENCIES = (ParentNodeProvider,)

    VALID = [
        Valid("import os\n"),
        Valid("from pathlib import Path\n"),
        Valid("from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import os\n"),
        Valid(
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n"
            "    from pathlib import Path\n"
        ),
        Valid("import typing\n\nif typing.TYPE_CHECKING:\n    import os\n"),
    ]

    INVALID = [
        Invalid("def example():\n    import os\n"),
        Invalid("class Example:\n    import os\n"),
        Invalid("if enabled:\n    import os\n"),
        Invalid("def example():\n    from pathlib import Path\n"),
        Invalid("def example():\n    if TYPE_CHECKING:\n        import os\n"),
        Invalid("class Example:\n    if TYPE_CHECKING:\n        import os\n"),
        Invalid("if TYPE_CHECKING:\n    def example():\n        import os\n"),
        Invalid("if TYPE_CHECKING:\n    class Example:\n        import os\n"),
    ]

    def visit_Import(self, node: cst.Import) -> None:
        self._check_import(node)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self._check_import(node)

    def _check_import(self, node: cst.Import | cst.ImportFrom) -> None:
        if self._is_module_level(node) or self._is_in_type_checking_block(node):
            return

        self.report(node)

    def _is_module_level(self, node: cst.Import | cst.ImportFrom) -> bool:
        parent = self.get_metadata(ParentNodeProvider, node)
        grandparent = self.get_metadata(ParentNodeProvider, parent)

        return isinstance(parent, cst.SimpleStatementLine) and isinstance(
            grandparent,
            cst.Module,
        )

    def _is_in_type_checking_block(self, node: cst.Import | cst.ImportFrom) -> bool:
        statement = self.get_metadata(ParentNodeProvider, node)
        block = self.get_metadata(ParentNodeProvider, statement)
        parent = self.get_metadata(ParentNodeProvider, block)

        return (
            isinstance(statement, cst.SimpleStatementLine)
            and isinstance(block, cst.IndentedBlock)
            and isinstance(parent, cst.If)
            and self._is_type_checking_test(parent.test)
            and self._is_module_level_if(parent)
        )

    def _is_module_level_if(self, node: cst.If) -> bool:
        parent = self.get_metadata(ParentNodeProvider, node)

        return isinstance(parent, cst.Module)

    def _is_type_checking_test(self, test: cst.BaseExpression) -> bool:
        if isinstance(test, cst.Name):
            return test.value == "TYPE_CHECKING"

        return (
            isinstance(test, cst.Attribute)
            and isinstance(test.value, cst.Name)
            and test.value.value == "typing"
            and isinstance(test.attr, cst.Name)
            and test.attr.value == "TYPE_CHECKING"
        )

"""Unit tests for the markdown validator utility."""

import pytest

from pwi.utils.markdown import (
    IssueCategory,
    IssueSeverity,
    MarkdownValidator,
    ValidationIssue,
    validate_markdown,
)


class TestMarkdownValidator:
    """Tests for MarkdownValidator class."""

    def test_validate_valid_markdown(self) -> None:
        """Test validation of valid markdown content."""
        content = """# Test Document

## Section 1

This is a paragraph with **bold** and *italic* text.

- Item 1
- Item 2
- Item 3

```python
print("hello world")
```
"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        assert result.is_valid
        assert result.error_count == 0

    def test_detect_unclosed_code_block(self) -> None:
        """Test detection of unclosed code blocks."""
        content = """# Test

```python
def hello():
    print("world")
"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        assert not result.is_valid
        assert result.error_count >= 1

        code_block_issues = result.get_issues_by_category(IssueCategory.CODE_BLOCK)
        assert len(code_block_issues) >= 1
        assert "Unclosed" in code_block_issues[0].message

    def test_fix_unclosed_code_block(self) -> None:
        """Test auto-fixing of unclosed code blocks."""
        content = """# Test

```python
def hello():
    print("world")
"""
        validator = MarkdownValidator(fix_formatting=True)
        result = validator.validate(content)

        assert result.formatted_content is not None
        assert result.formatted_content.rstrip().endswith("```")

    def test_validate_mermaid_diagram(self) -> None:
        """Test validation of valid Mermaid diagrams."""
        content = """# Architecture

```mermaid
flowchart TD
    A[Start] --> B[Process]
    B --> C[End]
```
"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        # Should not have any mermaid errors
        mermaid_errors = [
            i for i in result.issues
            if i.category == IssueCategory.MERMAID and i.severity == IssueSeverity.ERROR
        ]
        assert len(mermaid_errors) == 0

    def test_detect_empty_mermaid_diagram(self) -> None:
        """Test detection of empty Mermaid diagrams."""
        content = """# Empty Diagram

```mermaid
```
"""
        validator = MarkdownValidator(strict_mermaid=True)
        result = validator.validate(content)

        mermaid_issues = result.get_issues_by_category(IssueCategory.MERMAID)
        assert len(mermaid_issues) >= 1
        assert any("Empty" in issue.message for issue in mermaid_issues)

    def test_detect_unknown_mermaid_type(self) -> None:
        """Test detection of unknown Mermaid diagram types."""
        content = """# Unknown Type

```mermaid
unknownDiagram
    A --> B
```
"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        mermaid_issues = result.get_issues_by_category(IssueCategory.MERMAID)
        assert any("Unknown" in issue.message for issue in mermaid_issues)

    def test_validate_table_columns(self) -> None:
        """Test validation of table column consistency."""
        content = """# Table Test

| Col1 | Col2 | Col3 |
|------|------|------|
| A    | B    | C    |
| D    | E    |
"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        table_issues = result.get_issues_by_category(IssueCategory.TABLE)
        # Should detect mismatched columns
        assert any("columns" in issue.message.lower() for issue in table_issues)

    def test_check_heading_hierarchy(self) -> None:
        """Test detection of skipped heading levels."""
        content = """# Main Title

#### Skipped to H4

Some content.
"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        heading_issues = result.get_issues_by_category(IssueCategory.HEADING)
        assert len(heading_issues) >= 1
        assert any("skipped" in issue.message.lower() for issue in heading_issues)

    def test_check_line_length(self) -> None:
        """Test detection of overly long lines."""
        long_line = "x" * 150
        content = f"""# Test

{long_line}
"""
        validator = MarkdownValidator(max_line_length=120)
        result = validator.validate(content)

        formatting_issues = result.get_issues_by_category(IssueCategory.FORMATTING)
        assert len(formatting_issues) >= 1
        assert any("exceeds" in issue.message.lower() for issue in formatting_issues)

    def test_skip_line_length_in_code_blocks(self) -> None:
        """Test that line length checks skip code blocks."""
        long_line = "x" * 150
        content = f"""# Test

```python
{long_line}
```
"""
        validator = MarkdownValidator(max_line_length=120)
        result = validator.validate(content)

        # Should not report line length issues for code blocks
        formatting_issues = [
            i for i in result.get_issues_by_category(IssueCategory.FORMATTING)
            if "exceeds" in i.message.lower()
        ]
        assert len(formatting_issues) == 0

    def test_validation_result_counts(self) -> None:
        """Test ValidationResult issue counting."""
        content = """# Test

```python
unclosed code
"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        assert result.error_count >= 1
        assert result.warning_count >= 0

    def test_validation_metadata(self) -> None:
        """Test that metadata is populated."""
        content = "# Test\n\nSome content."
        validator = MarkdownValidator()
        result = validator.validate(content)

        assert "line_count" in result.metadata
        assert "char_count" in result.metadata
        assert result.metadata["line_count"] == 3
        assert result.metadata["char_count"] == len(content)


class TestValidateMarkdownFunction:
    """Tests for the validate_markdown convenience function."""

    def test_convenience_function(self) -> None:
        """Test the validate_markdown convenience function."""
        content = "# Valid\n\nContent here."
        result = validate_markdown(content)

        assert result.is_valid

    def test_convenience_function_with_options(self) -> None:
        """Test convenience function with custom options."""
        content = "# Test\n\n" + ("x" * 100)
        result = validate_markdown(content, max_line_length=50)

        formatting_issues = result.get_issues_by_category(IssueCategory.FORMATTING)
        assert len(formatting_issues) >= 1


class TestValidationIssue:
    """Tests for ValidationIssue class."""

    def test_issue_string_representation(self) -> None:
        """Test string representation of validation issues."""
        issue = ValidationIssue(
            message="Test message",
            severity=IssueSeverity.ERROR,
            category=IssueCategory.SYNTAX,
            line=10,
        )

        str_repr = str(issue)
        assert "ERROR" in str_repr
        assert "syntax" in str_repr
        assert "Test message" in str_repr
        assert "line 10" in str_repr

    def test_issue_without_line_number(self) -> None:
        """Test issue string representation without line number."""
        issue = ValidationIssue(
            message="Test message",
            severity=IssueSeverity.WARNING,
            category=IssueCategory.STRUCTURE,
        )

        str_repr = str(issue)
        assert "unknown location" in str_repr


class TestMermaidValidation:
    """Tests specifically for Mermaid diagram validation."""

    @pytest.mark.parametrize(
        "diagram_type",
        [
            "graph",
            "flowchart",
            "sequenceDiagram",
            "classDiagram",
            "erDiagram",
            "gantt",
            "pie",
        ],
    )
    def test_valid_mermaid_types(self, diagram_type: str) -> None:
        """Test that valid Mermaid diagram types are recognized."""
        content = f"""```mermaid
{diagram_type}
    A --> B
```"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        # Should not report unknown type for valid types
        unknown_type_issues = [
            i for i in result.issues
            if "Unknown Mermaid diagram type" in i.message
        ]
        assert len(unknown_type_issues) == 0

    def test_mermaid_bracket_validation(self) -> None:
        """Test detection of unmatched brackets in Mermaid."""
        content = """```mermaid
flowchart TD
    A[Unclosed bracket
```"""
        validator = MarkdownValidator(strict_mermaid=True)
        result = validator.validate(content)

        mermaid_issues = result.get_issues_by_category(IssueCategory.MERMAID)
        assert any("bracket" in issue.message.lower() for issue in mermaid_issues)

    def test_er_diagram_validation(self) -> None:
        """Test validation of ER diagram syntax."""
        content = """```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE-ITEM : contains

    CUSTOMER {
        string id PK
        string name
    }
```"""
        validator = MarkdownValidator()
        result = validator.validate(content)

        # Should be valid
        mermaid_errors = [
            i for i in result.issues
            if i.category == IssueCategory.MERMAID and i.severity == IssueSeverity.ERROR
        ]
        assert len(mermaid_errors) == 0

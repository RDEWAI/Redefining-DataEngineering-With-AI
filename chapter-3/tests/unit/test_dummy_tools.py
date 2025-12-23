"""Unit tests for enterprise dummy tools.

Tests for Phase 7.5 - Enterprise Tool Scale Demonstration:
- T7.5-031: Create test_dummy_tools.py
- T7.5-032: Test generate_dummy_tools() returns exactly 100 tools
- T7.5-033: Test tools are distributed across 10 domains (10 each)
- T7.5-034: Test get_dummy_tool_functions() returns matching function count
- T7.5-035: Test mock functions return valid JSON structure
"""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.agentic.tools.dummy_tools import (  # noqa: E402
    DOMAIN_TOOLS,
    DummyTool,
    EnterpriseDomain,
    generate_dummy_tool_definitions,
    generate_dummy_tools,
    get_domain_tool_count,
    get_dummy_tool_functions,
    get_total_tool_count,
)


class TestDummyToolGeneration:
    """Tests for dummy tool generation functions."""

    def test_generate_dummy_tools_returns_100_tools(self):
        """T7.5-032: Test generate_dummy_tools() returns exactly 100 tools."""
        tools = generate_dummy_tools()
        assert len(tools) == 100, f"Expected 100 tools, got {len(tools)}"

    def test_tools_are_distributed_across_10_domains(self):
        """T7.5-033: Test tools are distributed across 10 domains (10 each)."""
        # Verify we have exactly 10 domains
        assert len(EnterpriseDomain) == 10, f"Expected 10 domains, got {len(EnterpriseDomain)}"

        # Verify each domain has exactly 10 tools
        domain_counts = get_domain_tool_count()
        for domain_name, count in domain_counts.items():
            assert count == 10, f"Domain {domain_name} has {count} tools, expected 10"

        # Verify total adds up to 100
        total = sum(domain_counts.values())
        assert total == 100, f"Total tools across domains is {total}, expected 100"

    def test_all_domains_present(self):
        """Verify all expected enterprise domains are present."""
        expected_domains = {
            "engineering",
            "data_platform",
            "security",
            "hr",
            "finance",
            "marketing",
            "sales",
            "support",
            "infrastructure",
            "ml_platform",
        }
        actual_domains = {d.value for d in EnterpriseDomain}
        assert actual_domains == expected_domains, f"Domain mismatch: {actual_domains}"

    def test_get_total_tool_count(self):
        """Verify get_total_tool_count() returns 100."""
        count = get_total_tool_count()
        assert count == 100, f"Expected 100, got {count}"

    def test_domain_filter_works(self):
        """Test filtering tools by domain."""
        # Get only Engineering tools
        eng_tools = generate_dummy_tools([EnterpriseDomain.ENGINEERING])
        assert len(eng_tools) == 10, f"Expected 10 engineering tools, got {len(eng_tools)}"

        # Verify all are Engineering domain
        for tool in eng_tools:
            assert tool.domain == EnterpriseDomain.ENGINEERING

    def test_multiple_domain_filter(self):
        """Test filtering tools by multiple domains."""
        tools = generate_dummy_tools([EnterpriseDomain.HR, EnterpriseDomain.FINANCE])
        assert len(tools) == 20, f"Expected 20 tools (HR + Finance), got {len(tools)}"


class TestDummyToolFunctions:
    """Tests for dummy tool function generation and execution."""

    def test_get_dummy_tool_functions_returns_matching_count(self):
        """T7.5-034: Test get_dummy_tool_functions() returns matching function count."""
        tools = generate_dummy_tools()
        functions = get_dummy_tool_functions()

        assert len(functions) == len(tools), (
            f"Function count ({len(functions)}) doesn't match tool count ({len(tools)})"
        )
        assert len(functions) == 100, f"Expected 100 functions, got {len(functions)}"

    def test_function_names_match_tool_names(self):
        """Verify function names match their corresponding tool names."""
        tools = generate_dummy_tools()
        functions = get_dummy_tool_functions()

        tool_names = {tool.name for tool in tools}
        function_names = set(functions.keys())

        assert tool_names == function_names, (
            f"Mismatch between tool names and function names: "
            f"Tools only: {tool_names - function_names}, "
            f"Functions only: {function_names - tool_names}"
        )

    def test_mock_functions_return_valid_json_structure(self):
        """T7.5-035: Test mock functions return valid JSON structure."""
        functions = get_dummy_tool_functions()

        # Test a sample of functions from different domains
        sample_tools = [
            ("engineering_run_build", {"project": "test-app"}),
            ("data_query_warehouse", {"query": "SELECT 1"}),
            ("security_scan_vulnerabilities", {"target": "repo", "scan_type": "sast"}),
            ("hr_get_employee_info", {"employee_id": "E001"}),
            ("finance_get_budget_status", {}),
        ]

        for tool_name, kwargs in sample_tools:
            func = functions[tool_name]
            result = func(**kwargs)

            # Verify required keys are present
            assert "success" in result, f"{tool_name}: missing 'success' key"
            assert "domain" in result, f"{tool_name}: missing 'domain' key"
            assert "tool" in result, f"{tool_name}: missing 'tool' key"
            assert "message" in result, f"{tool_name}: missing 'message' key"
            assert "input" in result, f"{tool_name}: missing 'input' key"
            assert "data" in result, f"{tool_name}: missing 'data' key"

            # Verify values
            assert result["success"] is True, f"{tool_name}: success should be True"
            assert isinstance(result["domain"], str), f"{tool_name}: domain should be string"
            assert result["tool"] == tool_name, f"{tool_name}: tool name mismatch"
            assert isinstance(result["message"], str), f"{tool_name}: message should be string"
            assert isinstance(result["input"], dict), f"{tool_name}: input should be dict"
            assert isinstance(result["data"], dict), f"{tool_name}: data should be dict"

            # Verify data contains mock and timestamp
            assert "mock" in result["data"], f"{tool_name}: data missing 'mock' key"
            assert result["data"]["mock"] is True, f"{tool_name}: mock should be True"
            assert "timestamp" in result["data"], f"{tool_name}: data missing 'timestamp' key"

    def test_all_functions_are_callable(self):
        """Verify all generated functions are callable."""
        functions = get_dummy_tool_functions()

        for name, func in functions.items():
            assert callable(func), f"Function {name} is not callable"

    def test_functions_handle_keyword_arguments(self):
        """Verify functions can receive keyword arguments."""
        functions = get_dummy_tool_functions()

        # Test with various argument patterns
        result = functions["engineering_run_build"](project="my-app", branch="develop")
        assert result["input"]["project"] == "my-app"
        assert result["input"]["branch"] == "develop"


class TestDummyToolDefinitions:
    """Tests for dummy tool definitions (LLM-compatible format)."""

    def test_generate_tool_definitions(self):
        """Test generating ToolDefinition objects."""
        definitions = generate_dummy_tool_definitions()

        assert len(definitions) == 100, f"Expected 100 definitions, got {len(definitions)}"

        # Verify structure of each definition
        for defn in definitions:
            assert hasattr(defn, "name"), "Definition missing 'name'"
            assert hasattr(defn, "description"), "Definition missing 'description'"
            assert hasattr(defn, "parameters"), "Definition missing 'parameters'"

            # Verify parameters is a valid schema
            assert isinstance(defn.parameters, dict), "parameters should be a dict"
            assert "type" in defn.parameters, "parameters missing 'type'"
            assert defn.parameters["type"] == "object", "parameters type should be 'object'"

    def test_tool_definitions_have_descriptions(self):
        """Verify all tool definitions have non-empty descriptions."""
        definitions = generate_dummy_tool_definitions()

        for defn in definitions:
            assert defn.description, f"Tool {defn.name} has empty description"
            assert len(defn.description) > 20, (
                f"Tool {defn.name} description too short: {len(defn.description)}"
            )

    def test_tool_definitions_openai_format(self):
        """Test conversion to OpenAI format."""
        definitions = generate_dummy_tool_definitions()

        for defn in definitions:
            openai_format = defn.to_openai_format()

            assert "type" in openai_format
            assert openai_format["type"] == "function"
            assert "function" in openai_format
            assert "name" in openai_format["function"]
            assert "description" in openai_format["function"]
            assert "parameters" in openai_format["function"]


class TestDummyToolDataclass:
    """Tests for DummyTool dataclass."""

    def test_dummy_tool_creation(self):
        """Test creating a DummyTool instance."""
        tool = DummyTool(
            name="test_tool",
            domain=EnterpriseDomain.ENGINEERING,
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
        )

        assert tool.name == "test_tool"
        assert tool.domain == EnterpriseDomain.ENGINEERING
        assert tool.is_mock is True

    def test_dummy_tool_execute(self):
        """Test DummyTool.execute() method."""
        tool = DummyTool(
            name="test_tool",
            domain=EnterpriseDomain.SECURITY,
            description="A test tool",
            input_schema={"type": "object", "properties": {}},
        )

        result = tool.execute(param1="value1", param2=123)

        assert result["success"] is True
        assert result["domain"] == "security"
        assert result["tool"] == "test_tool"
        assert result["input"]["param1"] == "value1"
        assert result["input"]["param2"] == 123

    def test_dummy_tool_to_tool_definition(self):
        """Test DummyTool.to_tool_definition() conversion."""
        tool = DummyTool(
            name="test_tool",
            domain=EnterpriseDomain.HR,
            description="A test HR tool for testing",
            input_schema={
                "type": "object",
                "properties": {"emp_id": {"type": "string"}},
                "required": ["emp_id"],
            },
        )

        defn = tool.to_tool_definition()

        assert defn.name == "test_tool"
        assert defn.description == "A test HR tool for testing"
        assert defn.parameters["required"] == ["emp_id"]


class TestDomainToolLists:
    """Tests for domain-specific tool lists."""

    def test_engineering_tools_count(self):
        """Test Engineering domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.ENGINEERING]) == 10

    def test_data_platform_tools_count(self):
        """Test Data Platform domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.DATA_PLATFORM]) == 10

    def test_security_tools_count(self):
        """Test Security domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.SECURITY]) == 10

    def test_hr_tools_count(self):
        """Test HR domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.HR]) == 10

    def test_finance_tools_count(self):
        """Test Finance domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.FINANCE]) == 10

    def test_marketing_tools_count(self):
        """Test Marketing domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.MARKETING]) == 10

    def test_sales_tools_count(self):
        """Test Sales domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.SALES]) == 10

    def test_support_tools_count(self):
        """Test Support domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.SUPPORT]) == 10

    def test_infrastructure_tools_count(self):
        """Test Infrastructure domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.INFRASTRUCTURE]) == 10

    def test_ml_platform_tools_count(self):
        """Test ML Platform domain has 10 tools."""
        assert len(DOMAIN_TOOLS[EnterpriseDomain.ML_PLATFORM]) == 10

    def test_unique_tool_names_across_domains(self):
        """Verify all tool names are unique across domains."""
        all_names = []
        for tools in DOMAIN_TOOLS.values():
            for tool in tools:
                all_names.append(tool.name)

        assert len(all_names) == len(set(all_names)), "Duplicate tool names found"


class TestTokenEfficiencyMetrics:
    """Tests to verify token efficiency claims."""

    def test_tool_description_length(self):
        """Verify tool descriptions are realistic length for token overhead demo."""
        tools = generate_dummy_tools()

        # Each tool should have a description of reasonable length
        for tool in tools:
            desc_len = len(tool.description)
            assert desc_len >= 50, f"Tool {tool.name} description too short ({desc_len} chars)"
            assert desc_len <= 300, f"Tool {tool.name} description too long ({desc_len} chars)"

    def test_input_schema_complexity(self):
        """Verify input schemas have realistic complexity."""
        tools = generate_dummy_tools()

        for tool in tools:
            schema = tool.input_schema
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema

            # Each tool should have at least one property
            props = schema.get("properties", {})
            assert len(props) >= 1, f"Tool {tool.name} has no properties"

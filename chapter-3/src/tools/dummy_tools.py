"""Enterprise dummy tools for demonstrating code execution token efficiency at scale.

This module generates 100 dummy tools across 10 enterprise domains to demonstrate
the token efficiency advantage of code execution over traditional tool calling.

From Anthropic's "Advanced Tool Use" paper:
    "The token overhead of tool definitions becomes increasingly significant as
    the number of tools grows. For enterprises with hundreds of tools across
    different teams, this can represent a substantial portion of the context budget."

Token Impact Analysis:
    - Traditional Mode: ~18,000 tokens for 100 tool definitions
    - Code Execution Mode: ~650 tokens for API stubs
    - Expected Reduction: 80-95% when dummy tools enabled

Example:
    >>> from src.tools.dummy_tools import generate_dummy_tools, get_dummy_tool_functions
    >>> tools = generate_dummy_tools()
    >>> len(tools)  # 100 tools
    100
    >>> funcs = get_dummy_tool_functions()
    >>> result = funcs["engineering_run_build"](project="my-app", branch="main")
    >>> result["success"]
    True
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from src.llm.base import ToolDefinition


class EnterpriseDomain(Enum):
    """Enterprise domain categories for dummy tools.

    Each domain represents a typical enterprise team owning different services.
    10 domains x 10 tools each = 100 total tools.
    """

    ENGINEERING = "engineering"
    DATA_PLATFORM = "data_platform"
    SECURITY = "security"
    HR = "hr"
    FINANCE = "finance"
    MARKETING = "marketing"
    SALES = "sales"
    SUPPORT = "support"
    INFRASTRUCTURE = "infrastructure"
    ML_PLATFORM = "ml_platform"


@dataclass
class DummyTool:
    """Enterprise dummy tool definition.

    Attributes:
        name: Tool identifier (e.g., "engineering_run_build")
        domain: Enterprise domain this tool belongs to
        description: Detailed tool description (50-100 words for realistic overhead)
        input_schema: JSON Schema for parameters
        is_mock: Always True for dummy tools
    """

    name: str
    domain: EnterpriseDomain
    description: str
    input_schema: dict[str, Any]
    is_mock: bool = True

    def to_tool_definition(self) -> ToolDefinition:
        """Convert to ToolDefinition for LLM tool calling."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.input_schema,
        )

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute mock tool (returns simulated response)."""
        return {
            "success": True,
            "domain": self.domain.value,
            "tool": self.name,
            "message": f"Mock response from {self.domain.value}.{self.name}",
            "input": kwargs,
            "data": {"mock": True, "timestamp": datetime.now().isoformat()},
        }


# =============================================================================
# ENGINEERING DOMAIN (CI/CD, Code Operations)
# =============================================================================
ENGINEERING_TOOLS: list[DummyTool] = [
    DummyTool(
        name="engineering_run_build",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Trigger a CI/CD build pipeline for the specified project. Starts the build "
            "process including compilation, unit tests, and artifact generation. Returns "
            "a build ID for tracking progress. Supports branch selection and custom "
            "environment variables."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name or repository path"},
                "branch": {
                    "type": "string",
                    "description": "Git branch to build",
                    "default": "main",
                },
                "env_vars": {
                    "type": "object",
                    "description": "Custom environment variables for the build",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["project"],
        },
    ),
    DummyTool(
        name="engineering_check_ci_status",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Check the current status of a CI/CD build or pipeline run. Returns detailed "
            "status including stage progress, test results summary, and estimated time "
            "remaining. Supports filtering by pipeline type."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "build_id": {"type": "string", "description": "Build or pipeline ID to check"},
                "include_logs": {
                    "type": "boolean",
                    "description": "Include recent log output",
                    "default": False,
                },
            },
            "required": ["build_id"],
        },
    ),
    DummyTool(
        name="engineering_trigger_deployment",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Deploy an application or service to the specified environment. Supports "
            "blue-green and canary deployment strategies. Requires approval for production "
            "deployments. Returns deployment tracking URL."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name to deploy"},
                "environment": {
                    "type": "string",
                    "enum": ["dev", "staging", "production"],
                    "description": "Target environment",
                },
                "version": {"type": "string", "description": "Version or commit SHA to deploy"},
                "strategy": {
                    "type": "string",
                    "enum": ["rolling", "blue-green", "canary"],
                    "default": "rolling",
                },
            },
            "required": ["service", "environment", "version"],
        },
    ),
    DummyTool(
        name="engineering_get_test_coverage",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Retrieve test coverage metrics for a project or repository. Returns line, "
            "branch, and function coverage percentages along with uncovered file list. "
            "Supports comparison with previous builds to track coverage trends."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "compare_to": {"type": "string", "description": "Build ID to compare against"},
            },
            "required": ["project"],
        },
    ),
    DummyTool(
        name="engineering_create_pr",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Create a pull request from the specified source branch to target branch. "
            "Automatically assigns reviewers based on CODEOWNERS and runs initial "
            "CI checks. Supports draft mode for work-in-progress changes."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "repository": {"type": "string", "description": "Repository path (org/repo)"},
                "source_branch": {"type": "string", "description": "Source branch name"},
                "target_branch": {
                    "type": "string",
                    "description": "Target branch",
                    "default": "main",
                },
                "title": {"type": "string", "description": "PR title"},
                "description": {"type": "string", "description": "PR description"},
                "draft": {"type": "boolean", "default": False},
            },
            "required": ["repository", "source_branch", "title"],
        },
    ),
    DummyTool(
        name="engineering_merge_pr",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Merge an approved pull request using the specified merge strategy. Validates "
            "all required checks have passed and approvals are complete. Supports squash, "
            "rebase, and merge commit strategies."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pr_number": {"type": "integer", "description": "Pull request number"},
                "repository": {"type": "string", "description": "Repository path"},
                "strategy": {
                    "type": "string",
                    "enum": ["merge", "squash", "rebase"],
                    "default": "squash",
                },
            },
            "required": ["pr_number", "repository"],
        },
    ),
    DummyTool(
        name="engineering_rollback_deployment",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Rollback a service to a previous deployment version. Creates an incident "
            "record and notifies the on-call team. Supports instant rollback to last "
            "known good version or specific version selection."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service to rollback"},
                "environment": {"type": "string", "enum": ["dev", "staging", "production"]},
                "target_version": {
                    "type": "string",
                    "description": "Version to rollback to (optional)",
                },
                "reason": {"type": "string", "description": "Reason for rollback"},
            },
            "required": ["service", "environment", "reason"],
        },
    ),
    DummyTool(
        name="engineering_get_release_notes",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Generate release notes for a version comparing commits between two tags. "
            "Automatically categorizes changes by type (feature, fix, breaking) and "
            "extracts contributor list. Supports markdown and JSON output formats."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "repository": {"type": "string", "description": "Repository path"},
                "from_tag": {"type": "string", "description": "Starting tag/commit"},
                "to_tag": {"type": "string", "description": "Ending tag/commit", "default": "HEAD"},
                "format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
            },
            "required": ["repository", "from_tag"],
        },
    ),
    DummyTool(
        name="engineering_get_dependencies",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Analyze project dependencies and check for security vulnerabilities. Returns "
            "dependency tree, outdated packages, and CVE alerts. Supports filtering by "
            "severity level and dependency type (direct vs transitive)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "severity_filter": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                },
                "include_dev": {"type": "boolean", "default": False},
            },
            "required": ["project"],
        },
    ),
    DummyTool(
        name="engineering_run_linter",
        domain=EnterpriseDomain.ENGINEERING,
        description=(
            "Run code linting and static analysis on a project or specific files. Returns "
            "violations grouped by rule with suggested fixes. Supports auto-fix mode for "
            "safe automatic corrections and custom rule configuration."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific files to lint",
                },
                "auto_fix": {"type": "boolean", "default": False},
                "rules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific rules to check",
                },
            },
            "required": ["project"],
        },
    ),
]

# =============================================================================
# DATA PLATFORM DOMAIN (Data Warehouse, Analytics)
# =============================================================================
DATA_PLATFORM_TOOLS: list[DummyTool] = [
    DummyTool(
        name="data_query_warehouse",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Execute SQL queries against the data warehouse. Supports standard SQL with "
            "warehouse-specific extensions. Returns results as JSON with schema metadata. "
            "Query execution is limited to 5 minutes with configurable row limits."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query to execute"},
                "warehouse": {
                    "type": "string",
                    "enum": ["analytics", "reporting", "raw"],
                    "default": "analytics",
                },
                "limit": {"type": "integer", "description": "Row limit", "default": 1000},
            },
            "required": ["query"],
        },
    ),
    DummyTool(
        name="data_get_lineage",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Retrieve data lineage graph for a table or column showing upstream and "
            "downstream dependencies. Includes transformation logic and freshness "
            "metadata. Supports depth limiting for complex pipelines."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Fully qualified table name (schema.table)",
                },
                "column": {"type": "string", "description": "Specific column (optional)"},
                "depth": {"type": "integer", "description": "Max traversal depth", "default": 3},
                "direction": {
                    "type": "string",
                    "enum": ["upstream", "downstream", "both"],
                    "default": "both",
                },
            },
            "required": ["table"],
        },
    ),
    DummyTool(
        name="data_validate_schema",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Validate proposed schema changes against existing data contracts. Checks "
            "for breaking changes, type compatibility, and downstream impact. Returns "
            "validation report with recommendations."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Target table name"},
                "proposed_schema": {"type": "object", "description": "New schema definition"},
                "breaking_changes_allowed": {"type": "boolean", "default": False},
            },
            "required": ["table", "proposed_schema"],
        },
    ),
    DummyTool(
        name="data_refresh_dashboard",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Trigger a refresh of dashboard data by rerunning underlying queries and "
            "materializations. Supports full or incremental refresh modes. Returns "
            "job ID for status tracking and estimated completion time."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "dashboard_id": {"type": "string", "description": "Dashboard identifier"},
                "mode": {
                    "type": "string",
                    "enum": ["full", "incremental"],
                    "default": "incremental",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "default": "normal",
                },
            },
            "required": ["dashboard_id"],
        },
    ),
    DummyTool(
        name="data_get_table_stats",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Get statistics and metadata for a warehouse table including row count, "
            "size, partition info, and query patterns. Returns freshness metrics and "
            "historical growth trends for capacity planning."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Fully qualified table name"},
                "include_samples": {
                    "type": "boolean",
                    "description": "Include sample rows",
                    "default": False,
                },
            },
            "required": ["table"],
        },
    ),
    DummyTool(
        name="data_run_dbt_model",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Execute dbt models with specified parameters. Supports single model or "
            "selector-based execution. Returns run results including test outcomes "
            "and materialization details."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Model name or selector"},
                "full_refresh": {"type": "boolean", "default": False},
                "vars": {"type": "object", "description": "Variables to pass to model"},
            },
            "required": ["model"],
        },
    ),
    DummyTool(
        name="data_create_snapshot",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Create a point-in-time snapshot of a table for historical analysis or "
            "compliance requirements. Stores snapshot with timestamp label. Supports "
            "scheduled automatic snapshots."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Source table name"},
                "snapshot_name": {"type": "string", "description": "Name for the snapshot"},
                "retention_days": {
                    "type": "integer",
                    "description": "Days to retain",
                    "default": 30,
                },
            },
            "required": ["table", "snapshot_name"],
        },
    ),
    DummyTool(
        name="data_get_query_history",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Retrieve query execution history with performance metrics. Returns query "
            "text, runtime, rows scanned, and cost estimates. Supports filtering by "
            "user, time range, and table accessed."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Filter by table accessed"},
                "user": {"type": "string", "description": "Filter by user"},
                "hours": {"type": "integer", "description": "Hours of history", "default": 24},
            },
            "required": [],
        },
    ),
    DummyTool(
        name="data_grant_access",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Grant read or write access to a dataset for a user or service account. "
            "Creates audit log entry and sends notification to data owner. Supports "
            "time-limited access grants."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "dataset": {"type": "string", "description": "Dataset name"},
                "grantee": {"type": "string", "description": "User or service account"},
                "permission": {"type": "string", "enum": ["read", "write", "admin"]},
                "expires_in_days": {"type": "integer", "description": "Access expiration"},
            },
            "required": ["dataset", "grantee", "permission"],
        },
    ),
    DummyTool(
        name="data_catalog_search",
        domain=EnterpriseDomain.DATA_PLATFORM,
        description=(
            "Search the data catalog for tables, columns, and datasets matching the "
            "query. Returns matches with descriptions, owners, and popularity scores. "
            "Supports faceted filtering by domain, type, and freshness."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "domain": {"type": "string", "description": "Filter by domain"},
                "type": {"type": "string", "enum": ["table", "view", "dataset"]},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    ),
]

# =============================================================================
# SECURITY DOMAIN (Compliance, Access Control)
# =============================================================================
SECURITY_TOOLS: list[DummyTool] = [
    DummyTool(
        name="security_scan_vulnerabilities",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Scan a repository or container image for security vulnerabilities. Returns "
            "CVE list with severity scores, affected versions, and remediation guidance. "
            "Supports scheduled scans and webhook notifications."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Repository path or image URI"},
                "scan_type": {"type": "string", "enum": ["sast", "dast", "sca", "container"]},
                "severity_threshold": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                },
            },
            "required": ["target", "scan_type"],
        },
    ),
    DummyTool(
        name="security_check_permissions",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Check access permissions for a user or service account across systems. "
            "Returns permission matrix with role assignments and inheritance. Supports "
            "comparison between users for access review."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "principal": {"type": "string", "description": "User or service account ID"},
                "resource": {"type": "string", "description": "Resource to check (optional)"},
                "include_inherited": {"type": "boolean", "default": True},
            },
            "required": ["principal"],
        },
    ),
    DummyTool(
        name="security_audit_logs",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Search and retrieve audit logs from security information system. Returns "
            "events matching criteria with actor, action, and resource details. Supports "
            "complex query filters and aggregation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or filter expression"},
                "start_time": {"type": "string", "description": "Start of time range (ISO 8601)"},
                "end_time": {"type": "string", "description": "End of time range (ISO 8601)"},
                "event_type": {"type": "string", "description": "Filter by event type"},
            },
            "required": ["query"],
        },
    ),
    DummyTool(
        name="security_rotate_secrets",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Rotate API keys, passwords, or certificates for a service. Updates all "
            "dependent configurations and invalidates old credentials. Creates audit "
            "trail and notifies service owners."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name"},
                "secret_type": {
                    "type": "string",
                    "enum": ["api_key", "password", "certificate", "token"],
                },
                "notify_owners": {"type": "boolean", "default": True},
            },
            "required": ["service", "secret_type"],
        },
    ),
    DummyTool(
        name="security_create_policy",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Create or update a security policy defining access rules for resources. "
            "Validates policy syntax and checks for conflicts with existing policies. "
            "Supports policy inheritance and condition expressions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "policy_name": {"type": "string", "description": "Policy identifier"},
                "rules": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Policy rules",
                },
                "scope": {"type": "string", "description": "Policy scope (org, project, resource)"},
            },
            "required": ["policy_name", "rules"],
        },
    ),
    DummyTool(
        name="security_compliance_check",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Run compliance check against specified framework (SOC2, GDPR, HIPAA). "
            "Returns control status with evidence and remediation recommendations. "
            "Supports continuous monitoring alerts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "framework": {
                    "type": "string",
                    "enum": ["SOC2", "GDPR", "HIPAA", "PCI-DSS", "ISO27001"],
                },
                "scope": {
                    "type": "string",
                    "description": "Scope of check (all or specific system)",
                },
                "include_evidence": {"type": "boolean", "default": True},
            },
            "required": ["framework"],
        },
    ),
    DummyTool(
        name="security_get_risk_score",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Calculate security risk score for a service or project. Combines vulnerability "
            "data, exposure metrics, and historical incident data. Returns score breakdown "
            "with contributing factors."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service or project name"},
                "include_dependencies": {"type": "boolean", "default": True},
            },
            "required": ["service"],
        },
    ),
    DummyTool(
        name="security_request_access",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Submit an access request for privileged resources. Routes to appropriate "
            "approvers based on resource sensitivity. Supports time-bound access and "
            "justification requirements."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "resource": {"type": "string", "description": "Resource identifier"},
                "access_level": {"type": "string", "enum": ["read", "write", "admin"]},
                "duration_hours": {"type": "integer", "description": "Requested access duration"},
                "justification": {"type": "string", "description": "Business justification"},
            },
            "required": ["resource", "access_level", "justification"],
        },
    ),
    DummyTool(
        name="security_incident_report",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Create or update a security incident report. Triggers incident response "
            "workflow based on severity. Tracks timeline, affected systems, and "
            "remediation actions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Incident title"},
                "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "description": {"type": "string", "description": "Detailed description"},
                "affected_systems": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "severity", "description"],
        },
    ),
    DummyTool(
        name="security_get_threat_intel",
        domain=EnterpriseDomain.SECURITY,
        description=(
            "Query threat intelligence database for IOCs, threat actors, or campaigns. "
            "Returns matching threat data with confidence scores and recommended actions. "
            "Supports integration with SIEM alerts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "indicator": {"type": "string", "description": "IOC to look up (IP, hash, domain)"},
                "indicator_type": {
                    "type": "string",
                    "enum": ["ip", "hash", "domain", "url", "email"],
                },
            },
            "required": ["indicator", "indicator_type"],
        },
    ),
]

# =============================================================================
# HR DOMAIN (Employee Data, Requests)
# =============================================================================
HR_TOOLS: list[DummyTool] = [
    DummyTool(
        name="hr_get_employee_info",
        domain=EnterpriseDomain.HR,
        description=(
            "Retrieve employee information from HR system. Returns profile data including "
            "department, manager, location, and start date. Respects data privacy settings "
            "and access controls."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID or email"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific fields to return",
                },
            },
            "required": ["employee_id"],
        },
    ),
    DummyTool(
        name="hr_submit_pto_request",
        domain=EnterpriseDomain.HR,
        description=(
            "Submit a paid time off request for approval. Validates against available "
            "balance and blackout dates. Routes to manager for approval with notification "
            "to team calendar."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "pto_type": {
                    "type": "string",
                    "enum": ["vacation", "sick", "personal", "bereavement"],
                },
                "notes": {"type": "string", "description": "Optional notes"},
            },
            "required": ["start_date", "end_date", "pto_type"],
        },
    ),
    DummyTool(
        name="hr_check_org_chart",
        domain=EnterpriseDomain.HR,
        description=(
            "Retrieve organizational chart starting from specified employee. Returns "
            "direct reports, manager chain, and team members. Supports depth limiting "
            "for large organizations."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID to center on"},
                "direction": {"type": "string", "enum": ["up", "down", "both"], "default": "both"},
                "depth": {"type": "integer", "description": "Levels to traverse", "default": 2},
            },
            "required": ["employee_id"],
        },
    ),
    DummyTool(
        name="hr_get_team_roster",
        domain=EnterpriseDomain.HR,
        description=(
            "Get roster of team members for a department or manager. Returns employee "
            "list with roles, locations, and working hours. Useful for scheduling and "
            "capacity planning."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "manager_id": {"type": "string", "description": "Manager employee ID"},
                "department": {"type": "string", "description": "Department name (alternative)"},
                "include_contractors": {"type": "boolean", "default": True},
            },
            "required": [],
        },
    ),
    DummyTool(
        name="hr_get_pto_balance",
        domain=EnterpriseDomain.HR,
        description=(
            "Check paid time off balance for an employee. Returns current balance by "
            "type with accrual schedule and pending requests. Includes year-to-date "
            "usage summary."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID (defaults to self)"},
                "year": {"type": "integer", "description": "Year to check"},
            },
            "required": [],
        },
    ),
    DummyTool(
        name="hr_update_profile",
        domain=EnterpriseDomain.HR,
        description=(
            "Update employee profile information such as contact details, emergency "
            "contacts, or dietary restrictions. Some fields require manager approval. "
            "Creates audit log of changes."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "field": {"type": "string", "description": "Field to update"},
                "value": {"type": "string", "description": "New value"},
                "effective_date": {"type": "string", "description": "When change takes effect"},
            },
            "required": ["field", "value"],
        },
    ),
    DummyTool(
        name="hr_submit_expense",
        domain=EnterpriseDomain.HR,
        description=(
            "Submit an expense report for reimbursement. Validates against policy limits "
            "and required receipts. Routes to appropriate approver based on amount and "
            "category."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["travel", "meals", "equipment", "training", "other"],
                },
                "amount": {"type": "number", "description": "Expense amount in USD"},
                "description": {"type": "string", "description": "Expense description"},
                "receipt_url": {"type": "string", "description": "URL to receipt image"},
                "date": {"type": "string", "description": "Expense date (YYYY-MM-DD)"},
            },
            "required": ["category", "amount", "description", "date"],
        },
    ),
    DummyTool(
        name="hr_book_meeting_room",
        domain=EnterpriseDomain.HR,
        description=(
            "Reserve a meeting room at specified location and time. Checks room capacity "
            "and AV equipment availability. Sends calendar invites to participants and "
            "confirmation to organizer."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "room_id": {"type": "string", "description": "Room identifier"},
                "start_time": {"type": "string", "description": "Meeting start (ISO 8601)"},
                "duration_minutes": {"type": "integer", "description": "Meeting duration"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Attendee emails",
                },
                "equipment": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required equipment",
                },
            },
            "required": ["room_id", "start_time", "duration_minutes"],
        },
    ),
    DummyTool(
        name="hr_get_holiday_calendar",
        domain=EnterpriseDomain.HR,
        description=(
            "Retrieve company holiday calendar for specified region and year. Returns "
            "holiday dates with optional days and office closure information. Supports "
            "filtering by location."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Calendar year"},
                "region": {"type": "string", "description": "Office region/country"},
            },
            "required": ["year"],
        },
    ),
    DummyTool(
        name="hr_submit_feedback",
        domain=EnterpriseDomain.HR,
        description=(
            "Submit performance feedback for a colleague. Supports 360-degree feedback "
            "cycles and peer recognition. Anonymous option available for sensitive "
            "feedback."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "recipient_id": {"type": "string", "description": "Employee receiving feedback"},
                "feedback_type": {
                    "type": "string",
                    "enum": ["recognition", "constructive", "360_review"],
                },
                "message": {"type": "string", "description": "Feedback content"},
                "anonymous": {"type": "boolean", "default": False},
            },
            "required": ["recipient_id", "feedback_type", "message"],
        },
    ),
]

# =============================================================================
# FINANCE DOMAIN (Budget, Expense Management)
# =============================================================================
FINANCE_TOOLS: list[DummyTool] = [
    DummyTool(
        name="finance_get_budget_status",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Check budget status for a cost center or project. Returns allocated amount, "
            "spent to date, committed spend, and remaining balance. Includes variance "
            "analysis against forecast."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "cost_center": {"type": "string", "description": "Cost center code"},
                "project_id": {"type": "string", "description": "Project ID (alternative)"},
                "fiscal_year": {"type": "integer", "description": "Fiscal year"},
                "quarter": {"type": "integer", "description": "Specific quarter (1-4)"},
            },
            "required": [],
        },
    ),
    DummyTool(
        name="finance_submit_expense",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Submit an expense claim for reimbursement through finance system. Applies "
            "tax calculations and policy validation. Tracks approval workflow and "
            "payment status."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Expense amount"},
                "currency": {"type": "string", "description": "Currency code", "default": "USD"},
                "category": {"type": "string", "description": "Expense category"},
                "project_code": {"type": "string", "description": "Project to charge"},
                "receipt_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Receipt document IDs",
                },
            },
            "required": ["amount", "category", "project_code"],
        },
    ),
    DummyTool(
        name="finance_generate_invoice",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Generate an invoice for a customer or project milestone. Pulls line items "
            "from time tracking and approved expenses. Applies contract terms and "
            "payment schedules."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer identifier"},
                "project_id": {"type": "string", "description": "Project for billing"},
                "line_items": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Invoice line items",
                },
                "due_days": {
                    "type": "integer",
                    "description": "Payment terms in days",
                    "default": 30,
                },
            },
            "required": ["customer_id", "line_items"],
        },
    ),
    DummyTool(
        name="finance_check_payment_status",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Check status of a payment request or invoice. Returns current status, "
            "approval chain progress, and estimated payment date. Supports batch "
            "status checks."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "payment_id": {"type": "string", "description": "Payment or invoice ID"},
                "type": {"type": "string", "enum": ["expense", "invoice", "purchase_order"]},
            },
            "required": ["payment_id", "type"],
        },
    ),
    DummyTool(
        name="finance_create_purchase_order",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Create a purchase order for vendor goods or services. Validates against "
            "budget availability and preferred vendor list. Routes for approval based "
            "on amount thresholds."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string", "description": "Vendor identifier"},
                "items": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Line items",
                },
                "cost_center": {"type": "string", "description": "Charging cost center"},
                "delivery_date": {"type": "string", "description": "Requested delivery date"},
            },
            "required": ["vendor_id", "items", "cost_center"],
        },
    ),
    DummyTool(
        name="finance_get_spending_report",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Generate spending analysis report for a time period. Breaks down expenses "
            "by category, vendor, and department. Includes trend analysis and anomaly "
            "detection alerts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Report start date"},
                "end_date": {"type": "string", "description": "Report end date"},
                "group_by": {
                    "type": "string",
                    "enum": ["category", "vendor", "department", "project"],
                },
                "cost_center": {"type": "string", "description": "Filter to cost center"},
            },
            "required": ["start_date", "end_date", "group_by"],
        },
    ),
    DummyTool(
        name="finance_approve_request",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Approve or reject a pending financial request (expense, PO, invoice). "
            "Records decision with optional comments. Triggers next approval step "
            "or payment processing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "Request identifier"},
                "decision": {"type": "string", "enum": ["approve", "reject", "request_info"]},
                "comments": {"type": "string", "description": "Decision comments"},
            },
            "required": ["request_id", "decision"],
        },
    ),
    DummyTool(
        name="finance_forecast_budget",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Generate budget forecast based on current spending trends. Projects "
            "end-of-period spend with confidence intervals. Identifies categories "
            "at risk of overrun."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "cost_center": {"type": "string", "description": "Cost center to forecast"},
                "periods_ahead": {
                    "type": "integer",
                    "description": "Months to forecast",
                    "default": 3,
                },
                "scenario": {"type": "string", "enum": ["baseline", "optimistic", "pessimistic"]},
            },
            "required": ["cost_center"],
        },
    ),
    DummyTool(
        name="finance_get_vendor_info",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Retrieve vendor information including payment terms, contact details, "
            "and performance ratings. Shows historical spend and contract status. "
            "Indicates preferred vendor status."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string", "description": "Vendor identifier"},
                "include_contracts": {"type": "boolean", "default": True},
            },
            "required": ["vendor_id"],
        },
    ),
    DummyTool(
        name="finance_reconcile_account",
        domain=EnterpriseDomain.FINANCE,
        description=(
            "Initiate account reconciliation process. Compares transactions against "
            "bank statements and flags discrepancies. Supports automatic matching "
            "rules and manual review queue."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Account to reconcile"},
                "statement_date": {"type": "string", "description": "Statement date"},
                "auto_match": {"type": "boolean", "default": True},
            },
            "required": ["account_id", "statement_date"],
        },
    ),
]

# =============================================================================
# MARKETING DOMAIN (Campaigns, Content)
# =============================================================================
MARKETING_TOOLS: list[DummyTool] = [
    DummyTool(
        name="marketing_get_campaign_metrics",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Retrieve performance metrics for a marketing campaign. Returns impressions, "
            "clicks, conversions, and ROI by channel. Includes comparison to benchmarks "
            "and previous campaigns."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "campaign_id": {"type": "string", "description": "Campaign identifier"},
                "date_range": {"type": "string", "description": "Date range (7d, 30d, custom)"},
                "breakdown": {"type": "string", "enum": ["channel", "audience", "creative", "geo"]},
            },
            "required": ["campaign_id"],
        },
    ),
    DummyTool(
        name="marketing_schedule_post",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Schedule a social media post for publication. Supports multiple platforms "
            "with platform-specific formatting. Includes preview generation and optimal "
            "timing suggestions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Post content"},
                "platforms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Target platforms",
                },
                "scheduled_time": {"type": "string", "description": "Publication time (ISO 8601)"},
                "media_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Media attachments",
                },
            },
            "required": ["content", "platforms", "scheduled_time"],
        },
    ),
    DummyTool(
        name="marketing_analyze_sentiment",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Analyze sentiment of brand mentions or campaign responses. Uses NLP to "
            "classify positive, negative, and neutral sentiment. Returns trend analysis "
            "and notable mentions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Brand or topic to analyze"},
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Data sources",
                },
                "time_period": {"type": "string", "description": "Analysis period"},
            },
            "required": ["query"],
        },
    ),
    DummyTool(
        name="marketing_generate_report",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Generate comprehensive marketing performance report. Aggregates data from "
            "all channels with executive summary and recommendations. Supports custom "
            "templates and scheduling."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["weekly", "monthly", "quarterly", "campaign"],
                },
                "campaigns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Campaign IDs to include",
                },
                "format": {
                    "type": "string",
                    "enum": ["pdf", "pptx", "dashboard"],
                    "default": "pdf",
                },
            },
            "required": ["report_type"],
        },
    ),
    DummyTool(
        name="marketing_create_audience",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Create a target audience segment based on demographic and behavioral "
            "criteria. Estimates reach and overlap with existing audiences. Supports "
            "lookalike audience generation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Audience segment name"},
                "criteria": {"type": "object", "description": "Targeting criteria"},
                "platform": {"type": "string", "description": "Ad platform"},
            },
            "required": ["name", "criteria", "platform"],
        },
    ),
    DummyTool(
        name="marketing_get_ab_test_results",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Retrieve results from an A/B test experiment. Returns statistical "
            "significance, conversion lift, and confidence intervals. Recommends "
            "winning variant based on configured goals."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "test_id": {"type": "string", "description": "Test identifier"},
                "metric": {"type": "string", "description": "Primary success metric"},
            },
            "required": ["test_id"],
        },
    ),
    DummyTool(
        name="marketing_manage_content_calendar",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "View or update the content calendar. Shows scheduled posts, campaigns, "
            "and events by date. Supports drag-and-drop rescheduling and conflict "
            "detection."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["view", "add", "update", "delete"]},
                "date_range": {"type": "string", "description": "Calendar date range"},
                "entry": {"type": "object", "description": "Calendar entry for add/update"},
            },
            "required": ["action"],
        },
    ),
    DummyTool(
        name="marketing_get_competitor_insights",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Gather competitive intelligence on specified companies. Returns share of "
            "voice, content strategy analysis, and campaign tracking. Identifies "
            "opportunities and threats."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "competitors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Competitor names",
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to track",
                },
            },
            "required": ["competitors"],
        },
    ),
    DummyTool(
        name="marketing_email_campaign",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Create and send email marketing campaign. Supports list segmentation, "
            "personalization tokens, and A/B subject testing. Tracks opens, clicks, "
            "and conversions."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "template_id": {"type": "string", "description": "Email template"},
                "audience_id": {"type": "string", "description": "Target audience"},
                "subject": {"type": "string", "description": "Email subject line"},
                "schedule": {"type": "string", "description": "Send time (or 'now')"},
            },
            "required": ["template_id", "audience_id", "subject"],
        },
    ),
    DummyTool(
        name="marketing_track_attribution",
        domain=EnterpriseDomain.MARKETING,
        description=(
            "Analyze marketing attribution for conversions. Shows touchpoint journey "
            "and channel contribution using selected attribution model. Supports "
            "first-touch, last-touch, and multi-touch models."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "conversion_type": {
                    "type": "string",
                    "description": "Type of conversion to analyze",
                },
                "model": {
                    "type": "string",
                    "enum": ["first_touch", "last_touch", "linear", "time_decay"],
                },
                "date_range": {"type": "string", "description": "Analysis period"},
            },
            "required": ["conversion_type", "model"],
        },
    ),
]

# =============================================================================
# SALES DOMAIN (CRM, Pipeline)
# =============================================================================
SALES_TOOLS: list[DummyTool] = [
    DummyTool(
        name="sales_get_lead_details",
        domain=EnterpriseDomain.SALES,
        description=(
            "Retrieve detailed information about a sales lead. Returns contact info, "
            "company details, engagement history, and lead score. Includes next "
            "recommended action."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "Lead identifier"},
                "include_history": {"type": "boolean", "default": True},
            },
            "required": ["lead_id"],
        },
    ),
    DummyTool(
        name="sales_update_opportunity",
        domain=EnterpriseDomain.SALES,
        description=(
            "Update sales opportunity with new stage, amount, or close date. Records "
            "activity in opportunity timeline. Triggers pipeline recalculation and "
            "forecast update."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "opportunity_id": {"type": "string", "description": "Opportunity identifier"},
                "stage": {"type": "string", "description": "New pipeline stage"},
                "amount": {"type": "number", "description": "Updated deal value"},
                "close_date": {"type": "string", "description": "Expected close date"},
                "notes": {"type": "string", "description": "Update notes"},
            },
            "required": ["opportunity_id"],
        },
    ),
    DummyTool(
        name="sales_check_quota",
        domain=EnterpriseDomain.SALES,
        description=(
            "Check quota attainment for a sales rep or team. Returns target, closed "
            "amount, pipeline coverage, and pacing analysis. Includes comparison to "
            "peers and previous periods."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "rep_id": {
                    "type": "string",
                    "description": "Sales rep ID (or 'team' for team view)",
                },
                "period": {"type": "string", "description": "Quota period (Q1, Q2, etc.)"},
            },
            "required": ["period"],
        },
    ),
    DummyTool(
        name="sales_forecast_revenue",
        domain=EnterpriseDomain.SALES,
        description=(
            "Generate revenue forecast based on pipeline and historical conversion "
            "rates. Returns expected, best case, and commit forecasts with probability "
            "weighting. Identifies forecast risks."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Forecast period"},
                "segment": {"type": "string", "description": "Customer segment filter"},
                "confidence_level": {
                    "type": "number",
                    "description": "Minimum win probability",
                    "default": 0.5,
                },
            },
            "required": ["period"],
        },
    ),
    DummyTool(
        name="sales_create_quote",
        domain=EnterpriseDomain.SALES,
        description=(
            "Generate a sales quote with pricing and terms. Pulls products from catalog "
            "with applicable discounts. Supports approval workflow for non-standard "
            "pricing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "opportunity_id": {"type": "string", "description": "Associated opportunity"},
                "line_items": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Products and quantities",
                },
                "discount_pct": {"type": "number", "description": "Discount percentage"},
                "valid_days": {
                    "type": "integer",
                    "description": "Quote validity period",
                    "default": 30,
                },
            },
            "required": ["opportunity_id", "line_items"],
        },
    ),
    DummyTool(
        name="sales_log_activity",
        domain=EnterpriseDomain.SALES,
        description=(
            "Log a sales activity (call, email, meeting) against an account or "
            "opportunity. Automatically links to relevant records and updates "
            "last activity date."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "activity_type": {
                    "type": "string",
                    "enum": ["call", "email", "meeting", "demo", "other"],
                },
                "account_id": {"type": "string", "description": "Account identifier"},
                "opportunity_id": {"type": "string", "description": "Opportunity if applicable"},
                "subject": {"type": "string", "description": "Activity subject"},
                "notes": {"type": "string", "description": "Activity notes"},
                "duration_minutes": {"type": "integer", "description": "Activity duration"},
            },
            "required": ["activity_type", "subject"],
        },
    ),
    DummyTool(
        name="sales_get_pipeline_report",
        domain=EnterpriseDomain.SALES,
        description=(
            "Generate pipeline report showing opportunities by stage. Returns deal "
            "count, total value, and average age per stage. Includes stage conversion "
            "rates and stuck deal alerts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Sales rep or team"},
                "segment": {"type": "string", "description": "Customer segment filter"},
                "min_amount": {"type": "number", "description": "Minimum deal size"},
            },
            "required": [],
        },
    ),
    DummyTool(
        name="sales_search_accounts",
        domain=EnterpriseDomain.SALES,
        description=(
            "Search accounts by company name, industry, or custom criteria. Returns "
            "matching accounts with key metrics and owner assignment. Supports fuzzy "
            "matching and saved searches."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "industry": {"type": "string", "description": "Filter by industry"},
                "tier": {"type": "string", "enum": ["enterprise", "mid-market", "smb"]},
                "limit": {"type": "integer", "default": 25},
            },
            "required": ["query"],
        },
    ),
    DummyTool(
        name="sales_assign_territory",
        domain=EnterpriseDomain.SALES,
        description=(
            "Assign or reassign accounts to sales territories. Validates against "
            "territory rules and notifies affected reps. Supports bulk assignment "
            "for rebalancing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "account_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Accounts to assign",
                },
                "territory_id": {"type": "string", "description": "Target territory"},
                "effective_date": {"type": "string", "description": "Assignment effective date"},
            },
            "required": ["account_ids", "territory_id"],
        },
    ),
    DummyTool(
        name="sales_get_competitor_deals",
        domain=EnterpriseDomain.SALES,
        description=(
            "Track competitive deals and win/loss analysis. Returns deals where "
            "competitor was involved with outcome and lessons learned. Helps identify "
            "competitive displacement opportunities."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "competitor": {"type": "string", "description": "Competitor name"},
                "outcome": {"type": "string", "enum": ["won", "lost", "pending"]},
                "time_period": {"type": "string", "description": "Analysis period"},
            },
            "required": ["competitor"],
        },
    ),
]

# =============================================================================
# SUPPORT DOMAIN (Customer Service, Tickets)
# =============================================================================
SUPPORT_TOOLS: list[DummyTool] = [
    DummyTool(
        name="support_create_ticket",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Create a support ticket for a customer issue. Auto-assigns priority "
            "based on customer tier and issue type. Routes to appropriate queue "
            "with SLA tracking."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer identifier"},
                "subject": {"type": "string", "description": "Ticket subject"},
                "description": {"type": "string", "description": "Issue description"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "category": {"type": "string", "description": "Issue category"},
            },
            "required": ["customer_id", "subject", "description"],
        },
    ),
    DummyTool(
        name="support_get_ticket_status",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Check status and history of a support ticket. Returns current status, "
            "assignee, timeline of updates, and SLA status. Includes related tickets "
            "and customer context."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket number"},
                "include_comments": {"type": "boolean", "default": True},
            },
            "required": ["ticket_id"],
        },
    ),
    DummyTool(
        name="support_escalate_issue",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Escalate a ticket to higher support tier or management. Records "
            "escalation reason and notifies stakeholders. Adjusts SLA tracking "
            "to escalated service levels."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket to escalate"},
                "escalation_level": {
                    "type": "string",
                    "enum": ["tier2", "tier3", "management", "engineering"],
                },
                "reason": {"type": "string", "description": "Escalation reason"},
                "urgency": {"type": "string", "enum": ["normal", "high", "critical"]},
            },
            "required": ["ticket_id", "escalation_level", "reason"],
        },
    ),
    DummyTool(
        name="support_search_knowledge_base",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Search internal knowledge base for solutions and documentation. Uses "
            "semantic search to find relevant articles. Returns ranked results with "
            "article excerpts and links."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "category": {"type": "string", "description": "Article category filter"},
                "product": {"type": "string", "description": "Product filter"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    ),
    DummyTool(
        name="support_get_customer_history",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Retrieve support history for a customer. Returns past tickets, "
            "satisfaction scores, and interaction summary. Identifies patterns "
            "and recurring issues."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer identifier"},
                "days": {"type": "integer", "description": "Days of history", "default": 90},
            },
            "required": ["customer_id"],
        },
    ),
    DummyTool(
        name="support_add_ticket_comment",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Add a comment or update to a support ticket. Supports internal notes "
            "and customer-visible responses. Can include attachments and trigger "
            "notifications."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket number"},
                "comment": {"type": "string", "description": "Comment text"},
                "internal": {
                    "type": "boolean",
                    "description": "Internal note only",
                    "default": False,
                },
                "notify_customer": {"type": "boolean", "default": True},
            },
            "required": ["ticket_id", "comment"],
        },
    ),
    DummyTool(
        name="support_get_queue_metrics",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Get real-time metrics for support queues. Returns ticket counts, "
            "average wait time, SLA compliance, and agent availability. Supports "
            "filtering by team and priority."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "queue": {"type": "string", "description": "Queue name or 'all'"},
                "shift": {"type": "string", "enum": ["current", "24h", "7d"]},
            },
            "required": [],
        },
    ),
    DummyTool(
        name="support_merge_tickets",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Merge duplicate tickets into a single parent ticket. Preserves all "
            "comments and history. Notifies affected customers and updates "
            "reporting metrics."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "parent_ticket": {"type": "string", "description": "Ticket to keep"},
                "child_tickets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tickets to merge",
                },
            },
            "required": ["parent_ticket", "child_tickets"],
        },
    ),
    DummyTool(
        name="support_send_satisfaction_survey",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Send customer satisfaction survey after ticket resolution. Uses "
            "configurable survey template with NPS and CSAT questions. Results "
            "link to ticket for analysis."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Resolved ticket"},
                "survey_type": {
                    "type": "string",
                    "enum": ["nps", "csat", "ces"],
                    "default": "csat",
                },
                "delay_hours": {
                    "type": "integer",
                    "description": "Hours to wait before sending",
                    "default": 24,
                },
            },
            "required": ["ticket_id"],
        },
    ),
    DummyTool(
        name="support_create_kb_article",
        domain=EnterpriseDomain.SUPPORT,
        description=(
            "Create a new knowledge base article from ticket resolution. Extracts "
            "problem and solution into structured format. Routes for review before "
            "publication."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Source ticket"},
                "title": {"type": "string", "description": "Article title"},
                "category": {"type": "string", "description": "KB category"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Article tags",
                },
            },
            "required": ["ticket_id", "title", "category"],
        },
    ),
]

# =============================================================================
# INFRASTRUCTURE DOMAIN (DevOps, Monitoring)
# =============================================================================
INFRASTRUCTURE_TOOLS: list[DummyTool] = [
    DummyTool(
        name="infra_check_server_status",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Check health status of servers or services. Returns uptime, CPU, "
            "memory, and disk usage. Includes recent alerts and maintenance "
            "windows. Supports bulk status checks."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Hostname or service name"},
                "check_type": {"type": "string", "enum": ["quick", "detailed", "all"]},
            },
            "required": ["host"],
        },
    ),
    DummyTool(
        name="infra_scale_service",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Scale a service horizontally or vertically. Adjusts replica count "
            "or instance size. Performs gradual rollout with health checks. "
            "Records scaling event for analysis."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name"},
                "replicas": {"type": "integer", "description": "Target replica count"},
                "instance_type": {"type": "string", "description": "Instance size (for vertical)"},
                "strategy": {
                    "type": "string",
                    "enum": ["immediate", "gradual"],
                    "default": "gradual",
                },
            },
            "required": ["service"],
        },
    ),
    DummyTool(
        name="infra_get_metrics",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Query infrastructure metrics from monitoring system. Returns time "
            "series data for requested metrics with aggregation options. Supports "
            "PromQL-compatible queries."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Metric query (PromQL)"},
                "start_time": {"type": "string", "description": "Query start time"},
                "end_time": {"type": "string", "description": "Query end time"},
                "step": {"type": "string", "description": "Data point interval", "default": "1m"},
            },
            "required": ["query"],
        },
    ),
    DummyTool(
        name="infra_restart_container",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Restart a container or pod in the cluster. Performs graceful shutdown "
            "with configurable timeout. Verifies health after restart and reports "
            "status."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "container_id": {"type": "string", "description": "Container or pod ID"},
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "graceful_timeout": {
                    "type": "integer",
                    "description": "Shutdown timeout seconds",
                    "default": 30,
                },
            },
            "required": ["container_id"],
        },
    ),
    DummyTool(
        name="infra_create_alert",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Create or update an alerting rule for a metric. Configures threshold, "
            "evaluation window, and notification channels. Supports complex "
            "conditions with AND/OR logic."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Alert rule name"},
                "query": {"type": "string", "description": "Alert condition query"},
                "threshold": {"type": "number", "description": "Alert threshold"},
                "duration": {
                    "type": "string",
                    "description": "Condition duration",
                    "default": "5m",
                },
                "channels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Notification channels",
                },
            },
            "required": ["name", "query", "threshold"],
        },
    ),
    DummyTool(
        name="infra_get_logs",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Query application or system logs from centralized logging. Supports "
            "full-text search and structured queries. Returns logs with context "
            "and trace correlation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name"},
                "query": {"type": "string", "description": "Log search query"},
                "severity": {"type": "string", "enum": ["debug", "info", "warn", "error"]},
                "time_range": {"type": "string", "description": "Time range (1h, 24h, etc.)"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["service"],
        },
    ),
    DummyTool(
        name="infra_manage_dns",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Create, update, or delete DNS records. Supports A, CNAME, TXT, and "
            "other record types. Validates changes and provides rollback capability. "
            "Propagation status tracking."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "update", "delete"]},
                "domain": {"type": "string", "description": "Domain name"},
                "record_type": {"type": "string", "enum": ["A", "AAAA", "CNAME", "TXT", "MX"]},
                "value": {"type": "string", "description": "Record value"},
                "ttl": {"type": "integer", "description": "TTL in seconds", "default": 300},
            },
            "required": ["action", "domain", "record_type"],
        },
    ),
    DummyTool(
        name="infra_manage_ssl",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Manage SSL/TLS certificates for services. Check expiration, renew "
            "certificates, or upload custom certs. Integrates with Let's Encrypt "
            "for automatic renewal."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain for certificate"},
                "action": {"type": "string", "enum": ["check", "renew", "upload"]},
                "cert_data": {"type": "string", "description": "Certificate PEM (for upload)"},
            },
            "required": ["domain", "action"],
        },
    ),
    DummyTool(
        name="infra_get_cost_report",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Generate cloud infrastructure cost report. Breaks down spending by "
            "service, resource, and tag. Identifies cost anomalies and optimization "
            "opportunities."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Report period (7d, 30d, mtd)"},
                "group_by": {"type": "string", "enum": ["service", "tag", "account", "region"]},
                "compare_previous": {"type": "boolean", "default": True},
            },
            "required": ["period", "group_by"],
        },
    ),
    DummyTool(
        name="infra_run_maintenance",
        domain=EnterpriseDomain.INFRASTRUCTURE,
        description=(
            "Schedule or execute maintenance operation on infrastructure. Creates "
            "maintenance window, notifies stakeholders, and coordinates with "
            "monitoring to suppress alerts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target host or service"},
                "operation": {"type": "string", "description": "Maintenance type"},
                "scheduled_time": {"type": "string", "description": "Start time (ISO 8601)"},
                "duration_minutes": {"type": "integer", "description": "Expected duration"},
                "notify": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Notification recipients",
                },
            },
            "required": ["target", "operation", "scheduled_time", "duration_minutes"],
        },
    ),
]

# =============================================================================
# ML PLATFORM DOMAIN (AI/ML Operations)
# =============================================================================
ML_PLATFORM_TOOLS: list[DummyTool] = [
    DummyTool(
        name="ml_train_model",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Start a model training job with specified configuration. Provisions "
            "compute resources, tracks experiment metrics, and stores artifacts. "
            "Supports distributed training and hyperparameter tuning."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "Model identifier"},
                "dataset": {"type": "string", "description": "Training dataset path"},
                "config": {"type": "object", "description": "Training configuration"},
                "instance_type": {"type": "string", "description": "Compute instance type"},
                "distributed": {"type": "boolean", "default": False},
            },
            "required": ["model_name", "dataset", "config"],
        },
    ),
    DummyTool(
        name="ml_get_experiment_results",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Retrieve results from ML experiment or training run. Returns metrics, "
            "hyperparameters, and artifact locations. Supports comparison across "
            "multiple runs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "experiment_id": {"type": "string", "description": "Experiment identifier"},
                "run_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific runs to retrieve",
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to return",
                },
            },
            "required": ["experiment_id"],
        },
    ),
    DummyTool(
        name="ml_deploy_model",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Deploy a trained model to serving infrastructure. Creates endpoint "
            "with autoscaling configuration. Supports A/B testing and shadow mode "
            "deployment for validation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "Model to deploy"},
                "model_version": {"type": "string", "description": "Model version"},
                "endpoint_name": {"type": "string", "description": "Serving endpoint name"},
                "instance_count": {"type": "integer", "default": 1},
                "traffic_percent": {
                    "type": "integer",
                    "description": "Traffic percentage",
                    "default": 100,
                },
            },
            "required": ["model_name", "model_version", "endpoint_name"],
        },
    ),
    DummyTool(
        name="ml_monitor_predictions",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Monitor model predictions for data drift and performance degradation. "
            "Returns drift metrics, latency percentiles, and prediction distribution "
            "analysis. Alerts on threshold violations."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "endpoint": {"type": "string", "description": "Model endpoint name"},
                "time_range": {"type": "string", "description": "Monitoring window"},
                "baseline_dataset": {
                    "type": "string",
                    "description": "Reference dataset for drift detection",
                },
            },
            "required": ["endpoint"],
        },
    ),
    DummyTool(
        name="ml_register_model",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Register a trained model in the model registry. Records lineage, "
            "artifacts, and metadata. Supports model versioning and approval "
            "workflow for production promotion."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "Model name"},
                "artifact_path": {"type": "string", "description": "Model artifact location"},
                "metrics": {"type": "object", "description": "Model performance metrics"},
                "tags": {"type": "object", "description": "Model tags"},
                "description": {"type": "string", "description": "Model description"},
            },
            "required": ["model_name", "artifact_path"],
        },
    ),
    DummyTool(
        name="ml_get_feature_importance",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Calculate feature importance for a trained model. Returns ranked "
            "features with importance scores using SHAP or permutation importance. "
            "Supports visualization generation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "Model name"},
                "model_version": {"type": "string", "description": "Model version"},
                "method": {
                    "type": "string",
                    "enum": ["shap", "permutation", "gain"],
                    "default": "shap",
                },
                "sample_size": {"type": "integer", "default": 1000},
            },
            "required": ["model_name", "model_version"],
        },
    ),
    DummyTool(
        name="ml_create_dataset",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Create a versioned dataset for ML training or evaluation. Supports "
            "data validation, schema enforcement, and statistics computation. "
            "Tracks data lineage."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Dataset name"},
                "source": {"type": "string", "description": "Data source (path or query)"},
                "format": {"type": "string", "enum": ["parquet", "csv", "tfrecord"]},
                "validation_rules": {"type": "object", "description": "Data validation rules"},
            },
            "required": ["name", "source", "format"],
        },
    ),
    DummyTool(
        name="ml_run_batch_inference",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Execute batch inference job using a deployed model. Processes large "
            "datasets with configurable parallelism. Stores results with optional "
            "post-processing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "model_endpoint": {"type": "string", "description": "Model endpoint"},
                "input_dataset": {"type": "string", "description": "Input data path"},
                "output_path": {"type": "string", "description": "Output location"},
                "batch_size": {"type": "integer", "default": 100},
                "workers": {"type": "integer", "default": 4},
            },
            "required": ["model_endpoint", "input_dataset", "output_path"],
        },
    ),
    DummyTool(
        name="ml_compare_models",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Compare performance of multiple models on evaluation dataset. Returns "
            "side-by-side metrics, statistical significance tests, and recommendation "
            "for best model."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "models": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Models to compare (name + version)",
                },
                "eval_dataset": {"type": "string", "description": "Evaluation dataset"},
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to compare",
                },
            },
            "required": ["models", "eval_dataset"],
        },
    ),
    DummyTool(
        name="ml_explain_prediction",
        domain=EnterpriseDomain.ML_PLATFORM,
        description=(
            "Generate explanation for a single model prediction. Returns feature "
            "contributions, counterfactual examples, and confidence analysis. "
            "Supports various explainability methods."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "model_endpoint": {"type": "string", "description": "Model endpoint"},
                "input_data": {"type": "object", "description": "Input features for prediction"},
                "method": {
                    "type": "string",
                    "enum": ["shap", "lime", "anchors"],
                    "default": "shap",
                },
            },
            "required": ["model_endpoint", "input_data"],
        },
    ),
]


# =============================================================================
# AGGREGATION AND HELPER FUNCTIONS
# =============================================================================

# Mapping of domains to their tools
DOMAIN_TOOLS: dict[EnterpriseDomain, list[DummyTool]] = {
    EnterpriseDomain.ENGINEERING: ENGINEERING_TOOLS,
    EnterpriseDomain.DATA_PLATFORM: DATA_PLATFORM_TOOLS,
    EnterpriseDomain.SECURITY: SECURITY_TOOLS,
    EnterpriseDomain.HR: HR_TOOLS,
    EnterpriseDomain.FINANCE: FINANCE_TOOLS,
    EnterpriseDomain.MARKETING: MARKETING_TOOLS,
    EnterpriseDomain.SALES: SALES_TOOLS,
    EnterpriseDomain.SUPPORT: SUPPORT_TOOLS,
    EnterpriseDomain.INFRASTRUCTURE: INFRASTRUCTURE_TOOLS,
    EnterpriseDomain.ML_PLATFORM: ML_PLATFORM_TOOLS,
}


def generate_dummy_tools(domains: list[EnterpriseDomain] | None = None) -> list[DummyTool]:
    """Generate enterprise dummy tools, optionally filtered by domain.

    Args:
        domains: If provided, only include tools from these domains.
                 If None, includes all 100 tools from all 10 domains.

    Returns:
        List of DummyTool instances (100 total if no filter)

    Example:
        >>> tools = generate_dummy_tools()
        >>> len(tools)
        100
        >>> eng_tools = generate_dummy_tools([EnterpriseDomain.ENGINEERING])
        >>> len(eng_tools)
        10
    """
    if domains is None:
        domains = list(EnterpriseDomain)

    tools: list[DummyTool] = []
    for domain in domains:
        tools.extend(DOMAIN_TOOLS[domain])

    return tools


def generate_dummy_tool_definitions(
    domains: list[EnterpriseDomain] | None = None,
) -> list[ToolDefinition]:
    """Generate ToolDefinition objects for LLM tool calling.

    Args:
        domains: If provided, only include tools from these domains.

    Returns:
        List of ToolDefinition instances compatible with LLM APIs
    """
    return [tool.to_tool_definition() for tool in generate_dummy_tools(domains)]


def get_dummy_tool_functions(
    domains: list[EnterpriseDomain] | None = None,
) -> dict[str, Callable[..., dict[str, Any]]]:
    """Get dictionary of mock function implementations for dummy tools.

    Each mock function returns a realistic-looking JSON response with:
    - success: True
    - domain: The enterprise domain
    - tool: The tool name
    - message: A descriptive mock message
    - input: The input parameters received
    - data: Mock result data with timestamp

    Args:
        domains: If provided, only include tools from these domains.

    Returns:
        Dictionary mapping tool names to callable functions

    Example:
        >>> funcs = get_dummy_tool_functions()
        >>> result = funcs["engineering_run_build"](project="my-app")
        >>> result["success"]
        True
    """
    tools = generate_dummy_tools(domains)

    def create_mock_fn(tool: DummyTool) -> Callable[..., dict[str, Any]]:
        """Create a mock function for a tool."""

        def mock_fn(**kwargs: Any) -> dict[str, Any]:
            return tool.execute(**kwargs)

        mock_fn.__name__ = tool.name
        mock_fn.__doc__ = tool.description
        return mock_fn

    return {tool.name: create_mock_fn(tool) for tool in tools}


def get_domain_tool_count() -> dict[str, int]:
    """Get tool count per domain for verification.

    Returns:
        Dictionary mapping domain names to tool counts
    """
    return {domain.value: len(tools) for domain, tools in DOMAIN_TOOLS.items()}


def get_total_tool_count() -> int:
    """Get total count of all dummy tools.

    Returns:
        Total number of dummy tools (should be 100)
    """
    return sum(len(tools) for tools in DOMAIN_TOOLS.values())

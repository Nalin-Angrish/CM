"""Centralized tool definitions with JSON schemas.

This is the single source of truth for all available tools.
The LLM service fetches these dynamically via GET /tools.
To add new functionality, define the tool here and add its handler to main.py.
"""

TOOL_DEFINITIONS = [
    {
        "name": "create_s3_bucket",
        "description": "Create a new private Amazon S3 bucket",
        "parameters": {
            "type": "object",
            "required": ["bucket_name"],
            "properties": {
                "bucket_name": {
                    "type": "string",
                    "description": "Globally unique bucket name (3-63 lowercase chars, digits, hyphens)",
                },
                "versioning": {
                    "type": "boolean",
                    "description": "Enable versioning on the bucket",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "modify_s3_bucket",
        "description": "Modify an existing S3 bucket's configuration (versioning)",
        "parameters": {
            "type": "object",
            "required": ["bucket_name"],
            "properties": {
                "bucket_name": {
                    "type": "string",
                    "description": "Name of the S3 bucket to modify",
                },
                "versioning": {
                    "type": "boolean",
                    "description": "Enable or disable versioning",
                },
            },
        },
    },
    {
        "name": "delete_s3_bucket",
        "description": "Delete an S3 bucket and its contents",
        "parameters": {
            "type": "object",
            "required": ["bucket_name"],
            "properties": {
                "bucket_name": {
                    "type": "string",
                    "description": "Name of the S3 bucket to delete",
                },
            },
        },
    },
    {
        "name": "create_ec2_instance",
        "description": "Launch a new EC2 instance",
        "parameters": {
            "type": "object",
            "required": ["instance_name"],
            "properties": {
                "instance_name": {
                    "type": "string",
                    "description": "Name tag for the instance",
                },
                "instance_type": {
                    "type": "string",
                    "description": "EC2 instance type. Allowed: t2.micro, t2.small, t2.medium, t3.micro, t3.small, t3.medium",
                    "default": "t2.micro",
                },
                "ami_id": {
                    "type": "string",
                    "description": "AMI ID (defaults to Amazon Linux 2 for the region)",
                },
            },
        },
    },
    {
        "name": "modify_ec2_instance",
        "description": "Modify an existing EC2 instance (stop, start, or change type)",
        "parameters": {
            "type": "object",
            "required": ["instance_id", "action"],
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "The EC2 instance ID (e.g. i-0abc1234def56789)",
                },
                "action": {
                    "type": "string",
                    "description": "Action to perform: start, stop, or change_type",
                    "enum": ["start", "stop", "change_type"],
                },
                "instance_type": {
                    "type": "string",
                    "description": "New instance type (required when action is change_type)",
                },
            },
        },
    },
    {
        "name": "delete_ec2_instance",
        "description": "Terminate an EC2 instance permanently",
        "parameters": {
            "type": "object",
            "required": ["instance_id"],
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "The EC2 instance ID to terminate",
                },
            },
        },
    },
    {
        "name": "list_user_resources",
        "description": "List all cloud resources owned by the current user. Returns resource IDs, types, names, regions, and creation times.",
        "parameters": {
            "type": "object",
            "required": [],
            "properties": {
                "resource_type": {
                    "type": "string",
                    "description": "Filter by type: s3_bucket or ec2_instance",
                    "enum": ["s3_bucket", "ec2_instance"],
                },
            },
        },
    },
    {
        "name": "get_resource_details",
        "description": "Get detailed information about a specific resource by its name or ID",
        "parameters": {
            "type": "object",
            "required": [],
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "The resource UUID",
                },
                "name": {
                    "type": "string",
                    "description": "The resource name",
                },
            },
        },
    },
]


def get_tool_schemas() -> list[dict]:
    """Return the full tool definitions list for the /tools endpoint."""
    return TOOL_DEFINITIONS


def format_tools_for_prompt() -> str:
    """Format tool definitions as a readable string for LLM system prompts."""
    lines = []
    for tool in TOOL_DEFINITIONS:
        props = tool["parameters"].get("properties", {})
        required = set(tool["parameters"].get("required", []))
        param_parts = []
        for pname, pdef in props.items():
            req = " (required)" if pname in required else ""
            param_parts.append(f"{pname}: {pdef['type']}{req} - {pdef['description']}")
        params_str = "\n    ".join(param_parts) if param_parts else "none"
        lines.append(f"### {tool['name']}\n  {tool['description']}\n  Parameters:\n    {params_str}")
    return "\n\n".join(lines)

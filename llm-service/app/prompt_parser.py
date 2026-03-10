import json
import os
import re
import httpx

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8002")

# Cached tool text - refreshed on first request and on cache miss
_cached_tools_text: str | None = None

SYSTEM_PROMPT = """You are a cloud infrastructure assistant. You help users manage AWS resources (S3 buckets and EC2 instances) through natural conversation.

## Available Tools
{tools}

## User's Current Resources
{resources}

## Response Format
You MUST respond with ONLY a valid JSON object in one of these formats:

### 1. Execute a tool (you have all required parameters):
{{"type": "tool_call", "tool": "tool_name", "parameters": {{...}}}}

### 2. Ask for clarification (request is ambiguous or missing info):
{{"type": "clarification", "message": "your question", "options": ["option1", "option2"]}}

### 3. Conversational response (answering questions, explaining, guiding):
{{"type": "conversation", "message": "your response"}}

## Rules
1. ALWAYS check the user's resources list before modifying or deleting. Use resource names and cloud identifiers from the list.
2. If a user says "my instance" or "the test bucket", match against their resources. If multiple match, ask for clarification with the matching names.
3. If no resources match a delete/modify request, respond with a conversation message saying the resource was not found.
4. For creation without all details, suggest options and ask:
   - Instance size hints: "small" = t2.micro or t3.micro, "medium" = t2.small or t3.small, "big/large" = t2.medium or t3.medium
   - If no name given, ask what to name it
   - If purpose is mentioned, suggest appropriate instance types
5. Resources are created in the user's default AWS region (configured server-side). Do not ask for or accept a region parameter.
6. Public S3 access is BLOCKED by security policy. Never set public_access to true.
7. For resource information questions ("what do I have?", "tell me about my server"), respond with a conversation message summarizing the relevant resources from the list.
8. Keep responses focused on cloud infrastructure. Be concise and helpful.
9. Respond with ONLY the JSON object. No extra text.
10. CRITICAL - FOLLOW-UP HANDLING: When conversation history shows you previously asked a clarification question, the user's current message is their ANSWER to that question. You MUST use the full context from the previous exchange to complete the ORIGINAL action. Do NOT treat the answer as a new standalone request. Examples:
    - History: you asked "Which bucket to delete?" → User replies "my-logs" → Execute delete_s3_bucket with bucket_name "my-logs"
    - History: you asked "Which instance to stop?" → User replies "web-server" → Execute modify_ec2_instance to stop "web-server"
    - History: you asked "What instance type?" → User replies "t2.small" → Complete the ORIGINAL creation with instance_type t2.small
    The user's short reply is ALWAYS an answer to your last question, NOT a new request.
11. S3 bucket names CANNOT be changed after creation (AWS limitation). If asked to rename an S3 bucket, inform the user this is not possible and suggest creating a new bucket with the desired name and deleting the old one. NEVER call create_s3_bucket when the user asked to rename.
12. EC2 instance names can be updated by modifying the Name tag. However, the current tools do not support renaming. If asked to rename, inform the user and suggest the alternative. NEVER call create_ec2_instance when the user asked to rename.
13. Do NOT create a resource if the user asked to rename, modify, or delete one. The words "rename", "change name", "move", and "migrate" are NOT creation requests.
14. Do NOT create a resource with a name that already exists in the user's resources list. If the user asks to create a resource and a resource with the same name and type already exists, inform them that a resource with that name already exists."""


async def _fetch_tools_text() -> str:
    """Fetch formatted tool descriptions from the MCP server."""
    global _cached_tools_text
    if _cached_tools_text is not None:
        return _cached_tools_text
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{MCP_SERVER_URL}/tools/formatted")
            resp.raise_for_status()
            _cached_tools_text = resp.json()["formatted"]
            return _cached_tools_text
    except Exception:
        return _get_fallback_tools_text()


def _get_fallback_tools_text() -> str:
    """Hardcoded fallback if MCP is unreachable during prompt build."""
    return (
        "### create_s3_bucket\n  Create a new private S3 bucket\n"
        "  Parameters: bucket_name (required), versioning\n\n"
        "### modify_s3_bucket\n  Modify an S3 bucket\n"
        "  Parameters: bucket_name (required), versioning\n\n"
        "### delete_s3_bucket\n  Delete an S3 bucket\n"
        "  Parameters: bucket_name (required)\n\n"
        "### create_ec2_instance\n  Launch a new EC2 instance\n"
        "  Parameters: instance_name (required), instance_type\n\n"
        "### modify_ec2_instance\n  Modify an EC2 instance\n"
        "  Parameters: instance_id (required), action (required: start/stop/change_type), instance_type\n\n"
        "### delete_ec2_instance\n  Terminate an EC2 instance\n"
        "  Parameters: instance_id (required)\n\n"
        "### list_user_resources\n  List the user's cloud resources\n"
        "  Parameters: resource_type (optional: s3_bucket/ec2_instance)\n\n"
        "### get_resource_details\n  Get details of a specific resource\n"
        "  Parameters: resource_id or name"
    )


def _format_resources(resources: list[dict]) -> str:
    """Format the user's resource list for inclusion in the system prompt."""
    if not resources:
        return "No resources found. The user has not created any cloud resources yet."
    lines = []
    for r in resources:
        line = f"- {r['resource_type']}: \"{r['name']}\""
        if r.get("cloud_identifier"):
            line += f" (id: {r['cloud_identifier']})"
        if r.get("region"):
            line += f" in {r['region']}"
        if r.get("created_at"):
            line += f" [created: {r['created_at'][:10]}]"
        lines.append(line)
    return "\n".join(lines)


def _build_prompt(
    user_prompt: str,
    tools_text: str,
    resources: list[dict],
    conversation_history: list[dict] | None = None,
) -> str:
    """Build the full Llama 3.1 chat-template prompt."""
    system = SYSTEM_PROMPT.format(
        tools=tools_text,
        resources=_format_resources(resources),
    )
    parts = [
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n",
        system,
        "<|eot_id|>",
    ]

    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(
                f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
            )

    parts.append(
        f"<|start_header_id|>user<|end_header_id|>\n\n{user_prompt}<|eot_id|>"
    )
    parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    return "".join(parts)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output, handling markdown fences and noise."""
    text = text.strip()

    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            block = parts[1]
            if block.startswith(("json", "JSON")):
                block = block.split("\n", 1)[1] if "\n" in block else block[4:]
            text = block.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")


def _normalize_response(parsed: dict) -> dict:
    """Ensure the parsed LLM response has a valid type field."""
    if "type" not in parsed:
        if "tool" in parsed:
            parsed["type"] = "tool_call"
        elif "message" in parsed:
            parsed["type"] = "conversation"
        else:
            parsed["type"] = "tool_call"
    return parsed


async def parse_prompt(
    prompt: str,
    user_id: str,
    user_resources: list[dict] | None = None,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Parse a natural language prompt into a structured response via Ollama."""

    # ---- Follow-up resolution (deterministic, before LLM) ----
    # If the conversation history shows the assistant just asked a clarification
    # question, the user's current message is their answer.  Resolve it here
    # so we don't depend on the LLM (which often misinterprets short replies).
    followup = _resolve_followup(
        prompt.lower().strip(), user_resources or [], conversation_history
    )
    if followup is not None:
        return followup

    tools_text = await _fetch_tools_text()
    full_prompt = _build_prompt(
        prompt,
        tools_text,
        user_resources or [],
        conversation_history,
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": LOCAL_LLM_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1024,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("response", "")
            parsed = _extract_json(content)
            return _normalize_response(parsed)
    except (httpx.HTTPError, ValueError, KeyError):
        return _fallback_parse(prompt, user_resources or [], conversation_history)


def _resolve_followup(
    user_reply: str,
    resources: list[dict],
    conversation_history: list[dict] | None,
) -> dict | None:
    """If the conversation history shows a pending clarification, resolve it.

    Walks backwards through the history to find the last assistant message and
    the last user message before it.  When the assistant message looks like a
    clarification question we reconstruct the original intent from the earlier
    user message and combine it with the current user reply.

    Returns a parsed action dict, or None if this is not a follow-up.
    """
    if not conversation_history or len(conversation_history) < 2:
        return None

    # Find the last assistant message and the user message that preceded it.
    last_assistant: str | None = None
    original_user: str | None = None
    for msg in reversed(conversation_history):
        role = msg.get("role", "")
        content = msg.get("content", "")
        if last_assistant is None and role == "assistant":
            last_assistant = content.lower()
        elif last_assistant is not None and role == "user":
            original_user = content.lower()
            break

    if not last_assistant or not original_user:
        return None

    # Only treat as follow-up if the assistant message looks like a question.
    question_markers = ["which", "what", "do you", "would you", "?"]
    is_question = any(m in last_assistant for m in question_markers)
    if not is_question:
        return None

    # ---- Detect original operation from the earlier user message ----
    is_delete = any(w in original_user for w in ["delete", "remove", "destroy", "terminate"])
    is_modify = any(w in original_user for w in ["modify", "update", "change", "edit", "stop", "start", "enable", "disable"])
    is_create = any(w in original_user for w in ["create", "make", "launch", "new", "spin up"])
    is_s3 = any(w in original_user for w in ["s3", "bucket", "storage"])
    is_ec2 = any(w in original_user for w in ["ec2", "instance", "server", "vm"])

    if not (is_delete or is_modify or is_create):
        return None

    # The user_reply is typically a resource name or an option.  Try to match
    # it against the user's resource list.
    matched_resource = None
    for r in resources:
        if r["name"].lower() == user_reply or (
            r.get("cloud_identifier") and r["cloud_identifier"].lower() == user_reply
        ):
            matched_resource = r
            break

    # Also attempt a substring / partial match for cases like "website" matching "website".
    if not matched_resource:
        for r in resources:
            if user_reply in r["name"].lower() or r["name"].lower() in user_reply:
                matched_resource = r
                break

    # --- Delete ---
    if is_delete:
        if is_s3 or (matched_resource and matched_resource["resource_type"] == "s3_bucket"):
            bucket = (matched_resource["name"] if matched_resource else user_reply)
            return {
                "type": "tool_call",
                "tool": "delete_s3_bucket",
                "parameters": {"bucket_name": bucket},
            }
        if is_ec2 or (matched_resource and matched_resource["resource_type"] == "ec2_instance"):
            target = (
                matched_resource.get("cloud_identifier") or matched_resource["name"]
                if matched_resource
                else user_reply
            )
            return {
                "type": "tool_call",
                "tool": "delete_ec2_instance",
                "parameters": {"instance_id": target},
            }

    # --- Modify ---
    if is_modify:
        if is_ec2 or (matched_resource and matched_resource["resource_type"] == "ec2_instance"):
            target = (
                matched_resource.get("cloud_identifier") or matched_resource["name"]
                if matched_resource
                else user_reply
            )
            action = "stop" if "stop" in original_user else "start" if "start" in original_user else "change_type"
            params: dict = {"instance_id": target, "action": action}
            return {"type": "tool_call", "tool": "modify_ec2_instance", "parameters": params}
        if is_s3 or (matched_resource and matched_resource["resource_type"] == "s3_bucket"):
            bucket = (matched_resource["name"] if matched_resource else user_reply)
            params = {"bucket_name": bucket}
            if "versioning" in original_user:
                params["versioning"] = "enable" in original_user or "on" in original_user
            return {"type": "tool_call", "tool": "modify_s3_bucket", "parameters": params}

    # --- Create ---
    if is_create:
        # The user reply is likely the missing name or other parameter.
        if is_s3:
            return {
                "type": "tool_call",
                "tool": "create_s3_bucket",
                "parameters": {
                    "bucket_name": user_reply,
                    "versioning": "versioning" in original_user,
                },
            }
        if is_ec2:
            type_match = re.search(r"(t[23]\.(micro|small|medium))", original_user)
            instance_type = type_match.group(1) if type_match else "t2.micro"
            return {
                "type": "tool_call",
                "tool": "create_ec2_instance",
                "parameters": {
                    "instance_name": user_reply,
                    "instance_type": instance_type,
                },
            }

    return None


def _fallback_parse(prompt: str, resources: list[dict], conversation_history: list[dict] | None = None) -> dict:
    """Rule-based fallback parser when LLM is unavailable."""
    prompt_lower = prompt.lower().strip()

    # ------------------------------------------------------------------
    # Follow-up detection: if the last assistant message was a clarification
    # or question, treat the current prompt as the answer to that question.
    # We look at the conversation history to reconstruct the original intent.
    # ------------------------------------------------------------------
    pending_action = _resolve_followup(prompt_lower, resources, conversation_history)
    if pending_action is not None:
        return pending_action

    # Informational / listing queries
    info_words = ["list", "show", "view", "see", "what", "tell", "which", "how many", "describe"]
    if any(w in prompt_lower for w in info_words):
        resource_words = ["resource", "bucket", "instance", "server", "all", "have", "own"]
        if any(w in prompt_lower for w in resource_words):
            if resources:
                lines = []
                for r in resources:
                    cid = f" ({r.get('cloud_identifier', '')})" if r.get("cloud_identifier") else ""
                    lines.append(f"- {r['resource_type']}: {r['name']}{cid}")
                summary = "\n".join(lines)
                return {
                    "type": "conversation",
                    "message": f"Here are your current resources:\n{summary}",
                }
            return {
                "type": "conversation",
                "message": "You don't have any active resources.",
            }

    # Detect resource type
    is_s3 = any(w in prompt_lower for w in ["s3", "bucket", "storage"])
    is_ec2 = any(w in prompt_lower for w in ["ec2", "instance", "server", "vm"])

    # Detect operation
    is_rename = any(w in prompt_lower for w in ["rename", "change name", "change the name"])
    is_create = any(w in prompt_lower for w in ["create", "make", "launch", "new", "spin up"])
    is_delete = any(w in prompt_lower for w in ["delete", "remove", "destroy", "terminate"])
    is_modify = any(w in prompt_lower for w in ["modify", "update", "change", "edit", "stop", "start", "enable", "disable"])

    # Rename is not a create - intercept early
    if is_rename:
        if is_s3:
            return {
                "type": "conversation",
                "message": "S3 bucket names cannot be changed after creation (AWS limitation). "
                "You would need to create a new bucket with the desired name and then delete the old one.",
            }
        elif is_ec2:
            return {
                "type": "conversation",
                "message": "EC2 instance renaming is not supported by the current tools. "
                "You would need to create a new instance with the desired name and terminate the old one.",
            }
        return {
            "type": "conversation",
            "message": "Renaming is not supported for this resource type. "
            "You would need to create a new resource with the desired name and delete the old one.",
        }

    # Extract quoted or named identifiers
    name_match = re.search(r'(?:called|named|name)\s+["\']?([a-zA-Z0-9_-]+)["\']?', prompt_lower)
    name = name_match.group(1) if name_match else None

    # Resolve vague references against user resources for delete/modify
    if (is_delete or is_modify) and not name and resources:
        matching = resources
        if is_s3:
            matching = [r for r in resources if r["resource_type"] == "s3_bucket"]
        elif is_ec2:
            matching = [r for r in resources if r["resource_type"] == "ec2_instance"]

        if len(matching) == 1:
            r = matching[0]
            name = r.get("cloud_identifier") or r["name"]
        elif len(matching) > 1:
            names = [r["name"] for r in matching]
            return {
                "type": "clarification",
                "message": "You have multiple resources. Which one do you mean?",
                "options": names,
            }
        elif len(matching) == 0:
            return {
                "type": "conversation",
                "message": "I couldn't find any matching resources. Use 'list my resources' to see what you have.",
            }

    if is_s3:
        if is_create:
            if not name:
                return {
                    "type": "clarification",
                    "message": "What would you like to name the S3 bucket?",
                    "options": [],
                }
            versioning = "versioning" in prompt_lower
            return {
                "type": "tool_call",
                "tool": "create_s3_bucket",
                "parameters": {
                    "bucket_name": name,
                    "versioning": versioning,
                },
            }
        elif is_delete:
            return {
                "type": "tool_call",
                "tool": "delete_s3_bucket",
                "parameters": {"bucket_name": name or "unknown"},
            }
        elif is_modify:
            params = {"bucket_name": name or "unknown"}
            if "versioning" in prompt_lower:
                params["versioning"] = "enable" in prompt_lower or "on" in prompt_lower
            return {"type": "tool_call", "tool": "modify_s3_bucket", "parameters": params}

    if is_ec2:
        if is_create:
            if not name:
                return {
                    "type": "clarification",
                    "message": "What would you like to name this EC2 instance?",
                    "options": [],
                }
            type_match = re.search(r"(t[23]\.(micro|small|medium))", prompt_lower)
            instance_type = type_match.group(1) if type_match else None

            if not instance_type:
                if any(w in prompt_lower for w in ["big", "large", "powerful"]):
                    return {
                        "type": "clarification",
                        "message": f"For a larger instance named '{name}', I'd suggest one of these types:",
                        "options": ["t2.medium", "t3.medium"],
                    }
                elif any(w in prompt_lower for w in ["medium", "moderate"]):
                    return {
                        "type": "clarification",
                        "message": f"For a medium instance named '{name}', which type do you prefer?",
                        "options": ["t2.small", "t3.small"],
                    }
                else:
                    instance_type = "t2.micro"

            return {
                "type": "tool_call",
                "tool": "create_ec2_instance",
                "parameters": {
                    "instance_name": name,
                    "instance_type": instance_type,
                },
            }
        elif is_delete:
            target = name or "unknown"
            for r in resources:
                if r["name"] == target and r.get("cloud_identifier"):
                    target = r["cloud_identifier"]
                    break
            return {
                "type": "tool_call",
                "tool": "delete_ec2_instance",
                "parameters": {"instance_id": target},
            }
        elif is_modify:
            action = "stop" if "stop" in prompt_lower else "start" if "start" in prompt_lower else "change_type"
            target = name or "unknown"
            for r in resources:
                if r["name"] == target and r.get("cloud_identifier"):
                    target = r["cloud_identifier"]
                    break
            params = {"instance_id": target, "action": action}
            if action == "change_type":
                type_match = re.search(r"(t[23]\.(micro|small|medium))", prompt_lower)
                if type_match:
                    params["instance_type"] = type_match.group(1)
            return {"type": "tool_call", "tool": "modify_ec2_instance", "parameters": params}

    return {
        "type": "conversation",
        "message": "I can help you manage S3 buckets and EC2 instances. Try asking me to create, modify, delete, or list your resources.",
    }


INTERPRET_PROMPT = """You are a cloud infrastructure assistant. The user asked a question and a tool was executed to get data. Summarize the result in a helpful, concise, natural language response.

User's question: "{user_prompt}"
Tool executed: {tool_name}
Tool result:
{tool_result}

Respond with a clear, human-friendly summary. Use bullet points for lists. Do NOT output JSON - just plain text."""


async def interpret_result(
    user_prompt: str,
    tool_name: str,
    tool_result: dict,
    conversation_history: list[dict] | None = None,
) -> str:
    """Send tool output back through the LLM for natural language interpretation."""
    import json as _json

    result_str = _json.dumps(tool_result, indent=2, default=str)
    prompt_text = INTERPRET_PROMPT.format(
        user_prompt=user_prompt,
        tool_name=tool_name,
        tool_result=result_str,
    )

    parts = ["<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"]
    parts.append("You are a helpful cloud infrastructure assistant. Respond in plain text, not JSON.")
    parts.append("<|eot_id|>")

    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>")

    parts.append(f"<|start_header_id|>user<|end_header_id|>\n\n{prompt_text}<|eot_id|>")
    parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    full_prompt = "".join(parts)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": LOCAL_LLM_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 512},
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
    except Exception:
        return _fallback_interpret(tool_name, tool_result)


def _fallback_interpret(tool_name: str, tool_result: dict) -> str:
    """Plain-text fallback if LLM is unavailable for interpretation."""
    details = tool_result.get("details", {})
    message = tool_result.get("message", "")

    if tool_name == "list_user_resources":
        resources = details.get("resources", [])
        if not resources:
            return "You don't have any active resources."
        lines = [f"You have {len(resources)} active resource(s):"]
        for r in resources:
            cid = f" (ID: {r.get('cloud_identifier')})" if r.get("cloud_identifier") else ""
            lines.append(f"  - {r.get('resource_type', 'unknown')}: {r.get('name', 'unnamed')}{cid}")
        return "\n".join(lines)

    if tool_name == "get_resource_details":
        if not details:
            return "Resource not found."
        name = details.get("name", "unnamed")
        rtype = details.get("resource_type", "unknown")
        region = details.get("region", "unknown")
        status = details.get("status", "unknown")
        cid = details.get("cloud_identifier", "N/A")
        created = details.get("created_at", "unknown")[:10] if details.get("created_at") else "unknown"
        return (
            f"{rtype}: {name}\n"
            f"  Cloud ID: {cid}\n"
            f"  Region: {region}\n"
            f"  Status: {status}\n"
            f"  Created: {created}"
        )

    return message or "Operation completed."

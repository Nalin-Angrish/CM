import time
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import get_settings
from app.models.user import User
from app.models.prompt import Prompt
from app.models.resource import Resource
from app.models.execution_log import ExecutionLog
from app.auth.utils import get_current_user
from app.prompts.schemas import PromptRequest, PromptResponse

router = APIRouter(prefix="/api/prompts", tags=["prompts"])
settings = get_settings()

MODIFY_TOOLS = {"modify_s3_bucket", "modify_ec2_instance"}
DELETE_TOOLS = {"delete_s3_bucket", "delete_ec2_instance"}
CREATE_TOOLS = {"create_s3_bucket", "create_ec2_instance"}
QUERY_TOOLS = {"list_user_resources", "get_resource_details"}


async def _get_user_resources(db: AsyncSession, user: User) -> list[dict]:
    """Fetch active resources owned by the user for LLM context."""
    result = await db.execute(
        select(Resource)
        .where(Resource.user_id == user.id, Resource.status == "active")
        .order_by(Resource.created_at.desc())
    )
    resources = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "resource_type": r.resource_type,
            "cloud_identifier": r.cloud_identifier,
            "name": r.name,
            "region": r.region,
            "configuration": r.configuration or {},
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in resources
    ]


async def _check_ownership(
    db: AsyncSession, user: User, tool: str, params: dict
) -> Resource | None:
    """For modify/delete operations, verify the user owns the target resource."""
    resource_name = params.get("bucket_name") or params.get("instance_id") or params.get("name")
    if not resource_name:
        return None
    result = await db.execute(
        select(Resource).where(
            Resource.user_id == user.id,
            Resource.name == resource_name,
            Resource.status == "active",
        )
    )
    resource = result.scalar_one_or_none()
    if resource is None:
        result = await db.execute(
            select(Resource).where(
                Resource.user_id == user.id,
                Resource.cloud_identifier == resource_name,
                Resource.status == "active",
            )
        )
        resource = result.scalar_one_or_none()
    return resource


async def _llm_interpret(
    user_prompt: str,
    tool_name: str,
    tool_result: dict,
    history: list[dict],
    user_resources: list[dict],
) -> str:
    """Send tool output to LLM /interpret for a natural language summary."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.llm_service_url}/interpret",
                json={
                    "user_prompt": user_prompt,
                    "tool_name": tool_name,
                    "tool_result": tool_result,
                    "user_resources": user_resources,
                    "conversation_history": history,
                },
            )
            resp.raise_for_status()
            return resp.json().get("message", tool_result.get("message", "Done."))
    except Exception:
        return tool_result.get("message", "Operation completed.")


@router.post("", response_model=PromptResponse)
async def submit_prompt(
    body: PromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = Prompt(user_id=current_user.id, raw_text=body.prompt)
    db.add(prompt)
    await db.flush()

    start = time.time()

    user_resources = await _get_user_resources(db, current_user)
    history = [msg.model_dump() for msg in body.conversation_history]

    # Step 1: Parse prompt via LLM
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            llm_resp = await client.post(
                f"{settings.llm_service_url}/parse",
                json={
                    "prompt": body.prompt,
                    "user_id": str(current_user.id),
                    "user_resources": user_resources,
                    "conversation_history": history,
                },
            )
            llm_resp.raise_for_status()
            parsed = llm_resp.json()
    except httpx.HTTPError as e:
        prompt.status = "failed"
        prompt.error_message = f"LLM service error: {str(e)}"
        db.add(ExecutionLog(
            user_id=current_user.id, prompt_id=prompt.id,
            action="parse_prompt", status="failed",
            error_message=str(e),
            duration_ms=int((time.time() - start) * 1000),
        ))
        return PromptResponse(
            prompt_id=str(prompt.id), status="failed",
            response_type="tool_result", error=prompt.error_message,
        )

    response_type = parsed.get("type", "tool_call")
    tool_name = parsed.get("tool")
    tool_params = parsed.get("parameters", {})
    prompt.parsed_action = parsed

    # Step 2: Handle non-tool responses (clarification / conversation)
    if response_type in ("clarification", "conversation"):
        prompt.status = response_type
        db.add(ExecutionLog(
            user_id=current_user.id, prompt_id=prompt.id,
            action=response_type, status="success",
            result=parsed,
            duration_ms=int((time.time() - start) * 1000),
        ))
        return PromptResponse(
            prompt_id=str(prompt.id),
            status=response_type,
            response_type=response_type,
            parsed_action=parsed,
            message=parsed.get("message"),
            options=parsed.get("options", []),
        )

    # From here: tool_call
    prompt.status = "parsed"

    # Step 3: Query tools - execute via MCP then interpret
    if tool_name in QUERY_TOOLS:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                mcp_resp = await client.post(
                    f"{settings.mcp_server_url}/execute",
                    json={
                        "tool": tool_name,
                        "parameters": tool_params,
                        "user_id": str(current_user.id),
                    },
                )
                mcp_resp.raise_for_status()
                result = mcp_resp.json()
        except httpx.HTTPError:
            result = {
                "success": True,
                "message": f"Found {len(user_resources)} resource(s)",
                "details": {"resources": user_resources},
            }

        # Second LLM pass: interpret the raw result
        interpreted = await _llm_interpret(
            body.prompt, tool_name, result, history, user_resources
        )

        prompt.status = "completed"
        duration_ms = int((time.time() - start) * 1000)
        db.add(ExecutionLog(
            user_id=current_user.id, prompt_id=prompt.id,
            action=tool_name, tool_name=tool_name,
            tool_params=tool_params, result=result,
            status="success", duration_ms=duration_ms,
        ))
        return PromptResponse(
            prompt_id=str(prompt.id),
            status="completed",
            response_type="conversation",
            parsed_action=parsed,
            result=result,
            message=interpreted,
        )

    # Step 4: Ownership check for modify/delete
    if tool_name in MODIFY_TOOLS | DELETE_TOOLS:
        resource = await _check_ownership(db, current_user, tool_name, tool_params)
        if resource is None:
            prompt.status = "denied"
            prompt.error_message = "Resource not found or you do not own it"
            db.add(ExecutionLog(
                user_id=current_user.id, prompt_id=prompt.id,
                action=tool_name, tool_name=tool_name,
                tool_params=tool_params, status="denied",
                error_message=prompt.error_message,
                duration_ms=int((time.time() - start) * 1000),
            ))
            return PromptResponse(
                prompt_id=str(prompt.id), status="denied",
                response_type="tool_result",
                parsed_action=parsed, error=prompt.error_message,
            )

    # Step 5: Resource limit check for create
    if tool_name in CREATE_TOOLS:
        count_result = await db.execute(
            select(Resource).where(
                Resource.user_id == current_user.id, Resource.status == "active"
            )
        )
        active_count = len(count_result.scalars().all())
        if active_count >= current_user.max_resources:
            prompt.status = "denied"
            prompt.error_message = f"Resource limit reached ({current_user.max_resources})"
            return PromptResponse(
                prompt_id=str(prompt.id), status="denied",
                response_type="tool_result",
                parsed_action=parsed, error=prompt.error_message,
            )

        # Duplicate name check: reject creation if an active resource with the
        # same name and type already exists for this user.
        new_name = (
            tool_params.get("bucket_name")
            or tool_params.get("instance_name")
            or tool_params.get("name")
        )
        resource_type = "s3_bucket" if "s3" in tool_name else "ec2_instance"
        if new_name:
            dup_result = await db.execute(
                select(Resource).where(
                    Resource.user_id == current_user.id,
                    Resource.name == new_name,
                    Resource.resource_type == resource_type,
                    Resource.status == "active",
                )
            )
            if dup_result.scalar_one_or_none() is not None:
                prompt.status = "denied"
                prompt.error_message = (
                    f"A {resource_type.replace('_', ' ')} named '{new_name}' already exists"
                )
                return PromptResponse(
                    prompt_id=str(prompt.id), status="denied",
                    response_type="tool_result",
                    parsed_action=parsed, error=prompt.error_message,
                )

    # Step 6: Execute via MCP
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            mcp_resp = await client.post(
                f"{settings.mcp_server_url}/execute",
                json={
                    "tool": tool_name,
                    "parameters": tool_params,
                    "user_id": str(current_user.id),
                },
            )
            mcp_resp.raise_for_status()
            result = mcp_resp.json()
    except httpx.HTTPError as e:
        prompt.status = "failed"
        prompt.error_message = f"MCP execution error: {str(e)}"
        db.add(ExecutionLog(
            user_id=current_user.id, prompt_id=prompt.id,
            action=tool_name, tool_name=tool_name,
            tool_params=tool_params, status="failed",
            error_message=str(e),
            duration_ms=int((time.time() - start) * 1000),
        ))
        return PromptResponse(
            prompt_id=str(prompt.id), status="failed",
            response_type="tool_result",
            parsed_action=parsed, error=prompt.error_message,
        )

    duration_ms = int((time.time() - start) * 1000)
    prompt.status = "completed"

    # Step 7: Store resource record
    resource_id = None
    if tool_name in CREATE_TOOLS:
        resource_type = "s3_bucket" if "s3" in tool_name else "ec2_instance"
        resource = Resource(
            user_id=current_user.id,
            resource_type=resource_type,
            cloud_identifier=result.get("cloud_identifier"),
            name=tool_params.get("bucket_name")
            or tool_params.get("instance_name")
            or tool_params.get("name", "unnamed"),
            region=tool_params.get("region"),
            configuration=tool_params,
            status="active",
            creation_prompt_id=prompt.id,
        )
        db.add(resource)
        await db.flush()
        resource_id = resource.id
    elif tool_name in DELETE_TOOLS:
        resource = await _check_ownership(db, current_user, tool_name, tool_params)
        if resource:
            resource_id = resource.id
            resource.status = "deleted"
    else:
        resource = await _check_ownership(db, current_user, tool_name, tool_params)
        if resource:
            resource_id = resource.id

    db.add(ExecutionLog(
        user_id=current_user.id, prompt_id=prompt.id,
        resource_id=resource_id,
        action=tool_name, tool_name=tool_name,
        tool_params=tool_params, result=result,
        status="success", duration_ms=duration_ms,
    ))

    # Second LLM pass: interpret the action result
    interpreted = await _llm_interpret(
        body.prompt, tool_name, result, history, user_resources
    )

    return PromptResponse(
        prompt_id=str(prompt.id),
        status="completed",
        response_type="tool_result",
        parsed_action=parsed,
        result=result,
        message=interpreted,
    )


@router.get("", response_model=list[PromptResponse])
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Prompt)
        .where(Prompt.user_id == current_user.id)
        .order_by(Prompt.created_at.desc())
        .limit(50)
    )
    prompts = result.scalars().all()
    return [
        PromptResponse(
            prompt_id=str(p.id),
            status=p.status,
            parsed_action=p.parsed_action,
            error=p.error_message,
        )
        for p in prompts
    ]

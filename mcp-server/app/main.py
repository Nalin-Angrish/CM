import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from app.schemas import ToolRequest, ToolResponse
from app.tool_registry import get_tool_schemas, format_tools_for_prompt
from app.tools.s3_tools import create_s3_bucket, modify_s3_bucket, delete_s3_bucket
from app.tools.ec2_tools import create_ec2_instance, modify_ec2_instance, delete_ec2_instance
from app.tools.resource_tools import list_user_resources, get_resource_details
from app.validators import ValidationError
from app.database import get_pool, close_pool

# Handlers that take (params) only - sync AWS tools
SYNC_TOOLS = {
    "create_s3_bucket": create_s3_bucket,
    "modify_s3_bucket": modify_s3_bucket,
    "delete_s3_bucket": delete_s3_bucket,
    "create_ec2_instance": create_ec2_instance,
    "modify_ec2_instance": modify_ec2_instance,
    "delete_ec2_instance": delete_ec2_instance,
}

# Handlers that take (params, user_id) - async DB tools
ASYNC_TOOLS = {
    "list_user_resources": list_user_resources,
    "get_resource_details": get_resource_details,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(10):
        try:
            await get_pool()
            break
        except Exception:
            if attempt < 9:
                await asyncio.sleep(2)
            else:
                print("Warning: Could not connect to database. Resource tools will be unavailable.")
    yield
    await close_pool()


app = FastAPI(title="MCP Tool Server", version="2.0.0", lifespan=lifespan)


@app.post("/execute", response_model=ToolResponse)
async def execute_tool(request: ToolRequest):
    if request.tool in SYNC_TOOLS:
        handler = SYNC_TOOLS[request.tool]
        try:
            result = handler(request.parameters)
            return ToolResponse(**result)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")

    if request.tool in ASYNC_TOOLS:
        if not request.user_id:
            raise HTTPException(status_code=400, detail=f"Tool '{request.tool}' requires user_id")
        handler = ASYNC_TOOLS[request.tool]
        try:
            result = await handler(request.parameters, request.user_id)
            return ToolResponse(**result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")

    all_tools = list(SYNC_TOOLS.keys()) + list(ASYNC_TOOLS.keys())
    raise HTTPException(
        status_code=400,
        detail=f"Unknown tool: {request.tool}. Available: {all_tools}",
    )


@app.get("/tools")
async def list_tools():
    """Return full tool schemas for dynamic LLM prompt construction."""
    return {"tools": get_tool_schemas()}


@app.get("/tools/formatted")
async def get_formatted_tools():
    """Return tools as formatted text for direct insertion into LLM prompts."""
    return {"formatted": format_tools_for_prompt()}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp-server"}

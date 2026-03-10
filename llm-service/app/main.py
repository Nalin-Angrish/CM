import os
from fastapi import FastAPI
import httpx
from app.schemas import ParseRequest, ParseResponse, InterpretRequest, InterpretResponse
from app.prompt_parser import parse_prompt, interpret_result

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8002")

app = FastAPI(title="LLM Service", version="2.0.0")


@app.post("/parse", response_model=ParseResponse)
async def parse(request: ParseRequest):
    history = [msg.model_dump() for msg in request.conversation_history]
    result = await parse_prompt(
        prompt=request.prompt,
        user_id=request.user_id,
        user_resources=request.user_resources,
        conversation_history=history,
    )
    return ParseResponse(
        type=result.get("type", "tool_call"),
        tool=result.get("tool"),
        parameters=result.get("parameters", {}),
        message=result.get("message"),
        options=result.get("options", []),
    )


@app.post("/interpret", response_model=InterpretResponse)
async def interpret(request: InterpretRequest):
    history = [msg.model_dump() for msg in request.conversation_history]
    message = await interpret_result(
        user_prompt=request.user_prompt,
        tool_name=request.tool_name,
        tool_result=request.tool_result,
        conversation_history=history,
    )
    return InterpretResponse(message=message)


@app.get("/health")
async def health():
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            ollama_ok = resp.status_code == 200
    except httpx.HTTPError:
        pass

    mcp_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{MCP_SERVER_URL}/health")
            mcp_ok = resp.status_code == 200
    except httpx.HTTPError:
        pass

    return {
        "status": "ok",
        "service": "llm-service",
        "ollama_connected": ollama_ok,
        "mcp_connected": mcp_ok,
        "model": LOCAL_LLM_MODEL,
    }

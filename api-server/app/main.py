from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.auth.router import router as auth_router
from app.prompts.router import router as prompts_router
from app.resources.router import router as resources_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retry logic for database initialization (gives time for services to be ready)
    max_retries = 10
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database not ready, retrying ({attempt + 1}/{max_retries})...")
                await asyncio.sleep(2)
            else:
                print(f"Failed to initialize database after {max_retries} attempts")
                raise
    yield
    await engine.dispose()


app = FastAPI(
    title="Cloud Infrastructure Manager",
    version="1.0.0",
    description="Natural language cloud infrastructure management via MCP",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(prompts_router)
app.include_router(resources_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-server"}

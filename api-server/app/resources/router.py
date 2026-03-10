from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.resource import Resource
from app.models.execution_log import ExecutionLog
from app.auth.utils import get_current_user
from app.resources.schemas import ResourceResponse, ExecutionLogResponse

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("", response_model=list[ResourceResponse])
async def list_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Resource)
        .where(Resource.user_id == current_user.id, Resource.status == "active")
        .order_by(Resource.created_at.desc())
    )
    resources = result.scalars().all()
    return [
        ResourceResponse(
            id=str(r.id),
            resource_type=r.resource_type,
            cloud_identifier=r.cloud_identifier,
            name=r.name,
            region=r.region,
            configuration=r.configuration,
            status=r.status,
            created_at=r.created_at.isoformat(),
        )
        for r in resources
    ]


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id, Resource.user_id == current_user.id
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return ResourceResponse(
        id=str(resource.id),
        resource_type=resource.resource_type,
        cloud_identifier=resource.cloud_identifier,
        name=resource.name,
        region=resource.region,
        configuration=resource.configuration,
        status=resource.status,
        created_at=resource.created_at.isoformat(),
    )


@router.get("/logs/all", response_model=list[ExecutionLogResponse])
async def list_execution_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.user_id == current_user.id)
        .order_by(ExecutionLog.created_at.desc())
        .limit(100)
    )
    logs = result.scalars().all()
    return [
        ExecutionLogResponse(
            id=str(log.id),
            action=log.action,
            tool_name=log.tool_name,
            tool_params=log.tool_params,
            result=log.result,
            status=log.status,
            error_message=log.error_message,
            duration_ms=log.duration_ms,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]

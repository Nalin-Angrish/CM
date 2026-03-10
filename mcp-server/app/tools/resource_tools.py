"""Resource query tools - list and inspect resources owned by a user."""

import uuid
from app.database import get_pool


async def list_user_resources(params: dict, user_id: str) -> dict:
    """List active resources for the authenticated user."""
    pool = await get_pool()
    resource_type = params.get("resource_type")

    query = (
        "SELECT id, resource_type, cloud_identifier, name, region, "
        "configuration, status, created_at "
        "FROM resources WHERE user_id = $1 AND status = 'active'"
    )
    args: list = [uuid.UUID(user_id)]

    if resource_type:
        query += " AND resource_type = $2"
        args.append(resource_type)

    query += " ORDER BY created_at DESC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)

    resources = []
    for row in rows:
        resources.append(
            {
                "id": str(row["id"]),
                "resource_type": row["resource_type"],
                "cloud_identifier": row["cloud_identifier"],
                "name": row["name"],
                "region": row["region"],
                "configuration": dict(row["configuration"])
                if row["configuration"]
                else {},
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
            }
        )

    return {
        "success": True,
        "message": f"Found {len(resources)} active resource(s)",
        "details": {"resources": resources, "count": len(resources)},
    }


async def get_resource_details(params: dict, user_id: str) -> dict:
    """Get detailed info about a single resource by ID or name."""
    pool = await get_pool()
    resource_id = params.get("resource_id")
    name = params.get("name")

    if resource_id:
        query = (
            "SELECT id, resource_type, cloud_identifier, name, region, "
            "configuration, status, created_at, updated_at "
            "FROM resources WHERE id = $1 AND user_id = $2"
        )
        args: list = [uuid.UUID(resource_id), uuid.UUID(user_id)]
    elif name:
        query = (
            "SELECT id, resource_type, cloud_identifier, name, region, "
            "configuration, status, created_at, updated_at "
            "FROM resources WHERE name = $1 AND user_id = $2 AND status = 'active'"
        )
        args = [name, uuid.UUID(user_id)]
    else:
        return {
            "success": False,
            "message": "Either resource_id or name is required",
            "details": {},
        }

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)

    if row is None:
        return {
            "success": False,
            "message": "Resource not found or not owned by you",
            "details": {},
        }

    return {
        "success": True,
        "message": f"Details for '{row['name']}'",
        "details": {
            "id": str(row["id"]),
            "resource_type": row["resource_type"],
            "cloud_identifier": row["cloud_identifier"],
            "name": row["name"],
            "region": row["region"],
            "configuration": dict(row["configuration"])
            if row["configuration"]
            else {},
            "status": row["status"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        },
    }

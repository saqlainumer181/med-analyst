import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

from api.models.query import (
    QueryError,
    QueryHistory,
    QueryRequest,
    QueryResponse,
    SchemaInfo,
)
from core.database import db_manager, get_redis, schema_registry
from core.security import get_current_user, query_validator, rate_limit_dependency
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter()


@router.post(
    "/execute",
    response_model=QueryResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
async def execute_query(
    request: QueryRequest, current_user: Dict[str, Any] = Depends(get_current_user)
) -> QueryResponse:
    """Execute natural language query and return results"""
    query_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        # For Phase 1, return a mock response - will be replaced with actual NL2SQL in Phase 2
        mock_sql = "SELECT COUNT(*) as total_patients FROM patients;"

        # Validate the mock SQL
        query_validator.validate_query(mock_sql)

        # Execute query
        results = await db_manager.execute_query(mock_sql)

        # Convert asyncpg.Record to dict
        results_list = [dict(record) for record in results]

        execution_time = time.time() - start_time

        # Cache query result
        redis_client = await get_redis()
        cache_key = f"query:{query_id}"
        await redis_client.setex(
            cache_key,
            3600,  # 1 hour
            json.dumps(
                {
                    "query": request.query,
                    "sql": mock_sql,
                    "results": results_list,
                    "user_id": current_user["user_id"],
                }
            ),
        )

        response = QueryResponse(
            id=query_id,
            query=request.query,
            sql=mock_sql,
            results=results_list,
            execution_time=execution_time,
            row_count=len(results_list),
            timestamp=datetime.utcnow(),
            metadata={
                "user_id": current_user["user_id"],
                "query_type": request.query_type or "simple",
            },
        )

        return response

    except Exception as e:
        execution_time = time.time() - start_time
        error_response = QueryError(
            id=query_id,
            query=request.query,
            error=str(e),
            error_type=type(e).__name__,
            timestamp=datetime.utcnow(),
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_response.dict()
        )


@router.get("/history", response_model=List[QueryHistory])
async def get_query_history(
    limit: int = 20, current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[QueryHistory]:
    """Get user's query history"""
    try:
        redis_client = await get_redis()

        # Get cached queries for this user
        pattern = "query:*"
        keys = await redis_client.keys(pattern)

        history = []
        for key in keys[:limit]:
            cached_data = await redis_client.get(key)
            if cached_data:
                data = json.loads(cached_data)
                if data.get("user_id") == current_user["user_id"]:
                    history.append(
                        QueryHistory(
                            id=key.split(":")[-1],
                            user_id=data["user_id"],
                            query=data["query"],
                            sql=data["sql"],
                            status="completed",
                            execution_time=0.0,  # Not stored in cache for Phase 1
                            created_at=datetime.utcnow(),
                            row_count=len(data["results"]),
                        )
                    )

        return history[:limit]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get query history: {str(e)}",
        )


@router.get("/schema", response_model=SchemaInfo)
async def get_schema_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> SchemaInfo:
    """Get database schema information"""
    try:
        schema_data = await schema_registry.get_schema_info()

        tables = []
        relationships = []

        for table_name, table_info in schema_data.items():
            tables.append(
                {
                    "name": table_name,
                    "columns": table_info["columns"],
                    "primary_keys": table_info["primary_keys"],
                    "foreign_keys": table_info["foreign_keys"],
                }
            )

            # Extract relationships
            for fk in table_info["foreign_keys"]:
                relationships.append(
                    {
                        "from_table": table_name,
                        "from_column": fk,
                        "to_table": "referenced_table",  # Will be improved in Phase 2
                        "to_column": "referenced_column",
                    }
                )

        return SchemaInfo(
            tables=tables,
            relationships=relationships,
            total_tables=len(tables),
            last_updated=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schema info: {str(e)}",
        )


@router.get("/results/{query_id}")
async def get_query_results(
    query_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get cached query results by ID"""
    try:
        redis_client = await get_redis()
        cache_key = f"query:{query_id}"

        cached_data = await redis_client.get(cache_key)
        if not cached_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query results not found or expired",
            )

        data = json.loads(cached_data)

        # Check if user owns this query
        if data.get("user_id") != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this query",
            )

        return {
            "id": query_id,
            "query": data["query"],
            "sql": data["sql"],
            "results": data["results"],
            "row_count": len(data["results"]),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get query results: {str(e)}",
        )

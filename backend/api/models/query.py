from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, validator


class QueryType(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"
    REPORT = "report"


class QueryRequest(BaseModel):
    query: str
    include_report: bool = False
    query_type: Optional[QueryType] = None
    context: Optional[Dict[str, Any]] = None

    @validator("query")
    def validate_query(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError("Query must be at least 3 characters long")
        if len(v) > 5000:
            raise ValueError("Query too long (max 5000 characters)")
        return v.strip()


class QueryResponse(BaseModel):
    id: str
    query: str
    sql: str
    results: List[Dict[str, Any]]
    execution_time: float
    row_count: int
    status: str = "completed"
    timestamp: datetime
    report_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class QueryError(BaseModel):
    id: str
    query: str
    error: str
    error_type: str
    timestamp: datetime
    sql: Optional[str] = None


class SchemaInfo(BaseModel):
    tables: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    total_tables: int
    last_updated: datetime


class QueryHistory(BaseModel):
    id: str
    user_id: int
    query: str
    sql: str
    status: str
    execution_time: float
    created_at: datetime
    row_count: Optional[int] = None

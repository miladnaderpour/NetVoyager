"""Small public result contracts for source ingestion; no ORM or lifecycle semantics."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from netvoyager_schemas.imports import SourceDataset


class ImportIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    source_object_id: str | None = None


class ImportStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    total_rows: int = Field(ge=0)
    imported_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    warnings: int = Field(ge=0)
    errors: int = Field(ge=0)
    duplicate_serial_groups: int = Field(default=0, ge=0)
    shared_management_ip_groups: int = Field(default=0, ge=0)


class ImportResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dataset: SourceDataset
    issues: tuple[ImportIssue, ...] = ()
    statistics: ImportStatistics

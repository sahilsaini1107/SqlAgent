from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_catalog
from app.domain.schema_catalog import SchemaCatalog

router = APIRouter(prefix="/api", tags=["schema"])


class ColumnView(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool


class ForeignKeyView(BaseModel):
    column: str
    ref_table: str
    ref_column: str


class TableView(BaseModel):
    name: str
    columns: list[ColumnView]
    foreign_keys: list[ForeignKeyView]


class SchemaView(BaseModel):
    dialect: str
    tables: list[TableView]


@router.get("/schema", response_model=SchemaView)
def get_schema(catalog: SchemaCatalog = Depends(get_catalog)) -> SchemaView:
    """Return only the authorized schema metadata (no credentials, no system tables)."""
    return SchemaView(
        dialect="sqlite",
        tables=[
            TableView(
                name=table.name,
                columns=[
                    ColumnView(
                        name=col.name,
                        type=col.data_type,
                        nullable=col.nullable,
                        primary_key=col.primary_key,
                    )
                    for col in table.columns
                ],
                foreign_keys=[
                    ForeignKeyView(
                        column=fk.column, ref_table=fk.ref_table, ref_column=fk.ref_column
                    )
                    for fk in table.foreign_keys
                ],
            )
            for table in catalog.tables
        ],
    )

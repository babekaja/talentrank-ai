"""Compile all declared SQLAlchemy tables and indexes as MySQL DDL.

Pure compile check, WITHOUT connecting to a real MySQL server; does not certify
migration behavior, engine-specific foreign keys, or data integrity.
"""
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.schema import CreateIndex, CreateTable
from app.core.database import Base
from app import models  # noqa: F401


def check_schema():
    index_count=0
    for table in Base.metadata.sorted_tables:
        str(CreateTable(table).compile(dialect=dialect()))
        for index in table.indexes:
            str(CreateIndex(index).compile(dialect=dialect()))
            index_count+=1
    return {'tables':len(Base.metadata.tables),'indexes':index_count}


if __name__=='__main__':
    print('MySQL DDL compiled (offline only):', check_schema())

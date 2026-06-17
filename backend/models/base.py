from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy import MetaData

class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData()

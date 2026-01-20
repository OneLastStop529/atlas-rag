from sqlalchemy import Column, Integer, String, ForeignKey, Text, 
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base


import uuid 

Base = declarative_base()

class Documnet(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String, nullable=False) 


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Text, nullable=False)
    # embedding = Column(Text, nullable=False)  # Storing embedding as a string for simplicitkkkj

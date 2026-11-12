from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AuditResponse(BaseModel):
    id: str
    filename: str
    sha256_hash: str
    previous_hash: Optional[str] = None
    merkle_root: Optional[str] = None
    upload_time: datetime
    file_size: int
    uploader: Optional[str] = None
    source_ip: Optional[str] = None
    ingestion_mode: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


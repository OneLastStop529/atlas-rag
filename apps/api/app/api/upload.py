from fastapi import APIRouter, File, UploadFile
import uuid

router = APIRouter()

@router.post("/upload")
async def upload(file: UploadFile):
    return {
        "doc_id": str(uuid.uuid4()),
        "filename": file.filename,
        "status": "accepted"
    }


from fastapi import FastAPI 
from .api.chat import router as chat_router
from .api.upload import router as upload_router


app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(upload_router)

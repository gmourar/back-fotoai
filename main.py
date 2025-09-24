import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.config import settings
from db.database import init_db
from routes.photo_routes import router as photo_router
from routes.ai_routes import router as ai_router

app = FastAPI(title=settings.APP_NAME)

# CORS (ajuste conforme seu front)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(photo_router)
app.include_router(ai_router)
@app.on_event("startup")
async def on_startup():
    await init_db()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

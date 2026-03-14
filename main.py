from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from features.cartons.router import router as cartons_router
from features.layout.router import router as layout_router
from features.extract.router import router as extract_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cartons_router, prefix="/carton", tags=["Cartons"])
app.include_router(layout_router, prefix="/layout", tags=["Layout"])
app.include_router(extract_router, prefix="/extract", tags=["Extract"])

@app.get("/", tags=["Health"])
def root():
    return {
        "message": f"{settings.app_name} is running",
        "version": settings.app_version
    }
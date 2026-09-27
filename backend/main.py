from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router


app = FastAPI(
    title="RepoMind API",
    description="AI-powered repository reliability and bug validation system",
    version="1.0.0"
)

# Allow the Vite dev server (localhost:5173) to reach the backend.
# In production, replace "*" with the actual frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return{
        "message": "RepoMind backend is running"
    }

@app.get("/health")
def health_check():
    return{
        "status": "healthy",
        "service": "RepoMind backend"
    }
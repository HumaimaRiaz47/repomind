from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(
    title="RepoMind API",
    description="AI-powered repository reliability and bug validation system",
    version="1.0.0"
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
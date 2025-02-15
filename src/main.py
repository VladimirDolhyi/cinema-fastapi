import uvicorn
from fastapi import FastAPI

from src.routers import accounts

app = FastAPI()

app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

import uvicorn

from app.server import create_app

if __name__ == "__main__":
    uvicorn.run(create_app, factory=True, host="127.0.0.1", port=8000)

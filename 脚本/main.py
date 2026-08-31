from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="Musetopia API",
    description="一个简单的 FastAPI 服务",
    version="1.0.0"
)


class Message(BaseModel):
    content: str
    author: str = "Anonymous"


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Musetopia</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            a { color: #007bff; text-decoration: none; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>🎵 Musetopia</h1>
        <p>欢迎来到 Musetopia API 服务</p>

        <h2>可用端点</h2>
        <div class="endpoint"><strong>GET</strong> <a href="/api/hello">/api/hello</a> - Hello World</div>
        <div class="endpoint"><strong>GET</strong> <a href="/api/info">/api/info</a> - 服务信息</div>
        <div class="endpoint"><strong>POST</strong> /api/message - 发送消息</div>
        <div class="endpoint"><strong>GET</strong> <a href="/docs">/docs</a> - API 文档</div>
    </body>
    </html>
    """


@app.get("/api/hello")
async def hello():
    return {"message": "Hello, Musetopia!"}


@app.get("/api/info")
async def info():
    return {
        "name": "Musetopia API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/api/message")
async def create_message(msg: Message):
    return {
        "success": True,
        "received": {
            "content": msg.content,
            "author": msg.author
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

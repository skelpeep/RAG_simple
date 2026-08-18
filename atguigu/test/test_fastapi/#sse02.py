import uvicorn
from fastapi import FastAPI, Body
from pydantic import Field,BaseModel
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




class BodyParams(BaseModel):
    query: str = Field(...,description="查询内容")
    session_id: str = Field(...,description="会话ID")





@app.post("/sse02")
async def sse02(body_params: BodyParams = Body(...,description="请求体参数")):
    pass


if __name__ == '__main__':
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )




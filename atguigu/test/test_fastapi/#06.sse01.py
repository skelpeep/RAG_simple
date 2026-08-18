import time

import uvicorn
from fastapi import FastAPI, Query, BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from queue import Queue

from starlette.responses import StreamingResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

queue_dict = {}


def make_email(session_id:str):
    global queue_dict
    if not queue_dict.get(session_id):
        queue_dict[session_id] = Queue()
    q = queue_dict.get(session_id)
    q.put("你好01")
    q.put("你好02")
    q.put("你好03")
    q.put("你好04")
    q.put("你好05")
    q.put(None)



@app.get("/sse01")
async def sse01(
        background_tasks:BackgroundTasks,
        session_id:str = Query(...,description="会话id")
):
    background_tasks.add_task(make_email,session_id=session_id)
    return {"message":"收到"}



@app.get("/stream")
async def stream(session_id:str = Query(...,description="会话id")):
    def get_email():
        while not queue_dict.get(session_id):
            time.sleep(3)
        q = queue_dict.get(session_id)
        while True:
            email = q.get()
            yield f"data:{email}\n\n"
            if email is None:
                break
            time.sleep(1)
    return StreamingResponse(get_email(),media_type="text/event-stream")




if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)

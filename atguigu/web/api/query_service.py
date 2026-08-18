import json
import time
import uuid
from queue import Queue

import uvicorn
from fastapi import FastAPI, Path, Body, BackgroundTasks
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from atguigu.query_process.main_graph import MainGraphRunner
from atguigu.tool.mongo_client_tool import get_recent_history_list, clear_history
from atguigu.tool.task_utils import update_task_status, TASK_STATUS_PROCESSING, get_task_info, create_queue, \
    TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, put_data, get_data

app = FastAPI(
    title="检索模块对应的接口",
    description="检索模块对应的前端接口",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    #返回什么都行，只要res.ok=True即可，即返回200
    return {"aa": "bb"}

@app.get("/history/{session_id}")
async def get_history(session_id: str=Path(...,description="会话id")):
    history_list = get_recent_history_list(session_id)
    history_list=[
        {
            "_id":str(item.get("_id")),
            "role":item.get("role",""),
            "text":item.get("text",""),
            "rewritten_query":item.get("rewritten_query",""),
            "item_names":item.get("item_names",""),
            "ts":item.get("ts",""),
            "session_id":item.get("session_id",""),
            "image_urls":item.get("image_urls","")

        }
        for item in history_list
    ]
    history_list.sort(key=lambda a:a.get("ts"))
    return {"items":history_list}  # 前端读取 data.items，key 必须为复数

@app.delete("/history/{session_id}")
async def delete_history(session_id: str=Path(...,description="会话id")):
    clear_history(session_id)
    return {"msg":"删除成功"}



# queue_dict = {}

def run_main_graph(task_id:str,original_query:str,session_id:str):
    # if not queue_dict.get(task_id):
    #     queue_dict[task_id] =Queue()
    # q= queue_dict[task_id]

    create_queue(task_id)

    try:
        init_state = {
            "task_id": task_id,
            "original_query": original_query,
            "session_id": session_id,
            # "q":q
        }

        update_task_status(task_id,TASK_STATUS_PROCESSING)
        # q.put({"event":"progress","data":get_task_info(task_id)})

        put_data(task_id, event="progress", data=get_task_info(task_id))
        MainGraphRunner.create_and_run(init_state)
        update_task_status(task_id, TASK_STATUS_COMPLETED)
        # q.put({"event": "progress", "data": get_task_info(task_id)})
        put_data(task_id, event="progress", data=get_task_info(task_id))
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        # q.put({"event": "error", "data": get_task_info(task_id)})
        put_data(task_id, event="error", data=get_task_info(task_id))
        raise e

class QueryParams(BaseModel):
    query:str = Field(...,description="查询内容")
    session_id:str = Field(...,description="会话id")


@app.post("/query")
async def query(background_tasks:BackgroundTasks,query_params:QueryParams = Body(...,description="查询请求体参数")):
    task_id = str(uuid.uuid4())
    original_query = query_params.query
    session_id = query_params.session_id

    background_tasks.add_task(run_main_graph, task_id, original_query, session_id)



    return {
        "task_id":task_id,
        "original_query":original_query,
        "session_id":session_id
    }

def generate_stream(task_id):
    # while not queue_dict.get(task_id):
    #     time.sleep(1)
    # q = queue_dict[task_id]
    while True:
        item = get_data(task_id)
        time.sleep(0.05)
        yield f"event: {item.get('event')}\n"
        yield f"data: {json.dumps(item.get('data'),ensure_ascii=False)}\n\n"



@app.get("/stream/{task_id}")
async def stream(task_id: str = Path(...,description="任务id")):
    return StreamingResponse(generate_stream(task_id),media_type="text/event-stream")








if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)



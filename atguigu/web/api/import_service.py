import shutil
import uuid
from datetime import datetime
from pathlib import Path

import fastapi
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from starlette.middleware.cors import CORSMiddleware

from atguigu.config.config import ImportConfig, MinIoConfig
from atguigu.import_process.main_graph import MainGraphRunner
from atguigu.tool.logger import logger
from atguigu.tool.minio_client_tool import get_minio_client
from atguigu.tool.task_utils import update_task_status, TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, get_task_info, \
    add_running_task, add_done_task

app = FastAPI(
    title="掌柜智库导入模块对应接口服务",
    description="掌柜智库导入模块对应接口服务",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_main_graph(task_id:str,local_dir:str,local_file_path:str,user_metadata:dict=None,source_path:str=""):
    try:
        init_state = {
            "task_id": task_id,
            "local_dir": local_dir,
            "local_file_path": local_file_path,
            "user_metadata": user_metadata or {},
            "source_path": source_path,
        }
        update_task_status(task_id,TASK_STATUS_PROCESSING)
        MainGraphRunner.create_and_run(init_state)
        update_task_status(task_id, TASK_STATUS_COMPLETED)
    except Exception as e:
        logger.error(f"执行graph异常，task_id={task_id}")
        update_task_status(task_id, TASK_STATUS_FAILED)


@app.post("/upload")
async def upload_file(
        background_tasks:BackgroundTasks,
        file: UploadFile = File(...,description="上传的文件"),
        book_name: str = Form("", description="书名（可选，非空则覆盖自动识别）"),
        author: str = Form("", description="作者名（可选）"),
        content_type: str = Form("", description="内容类型（可选）"),
        category: str = Form("", description="类别/标签（可选）"),
        duration: str = Form("", description="有声书时长（可选）"),
):
    task_id = str(uuid.uuid4())

    add_running_task(task_id, "upload_file")

    date_str = datetime.now().strftime('%Y%m%d')
    local_dir = rf"{ImportConfig.output_dir}/{date_str}"
    local_dir_obj = Path(local_dir)
    if not local_dir_obj.exists():
        local_dir_obj.mkdir(parents=True,exist_ok=True)

    # 防止文件名携带路径分隔符，统一取文件名部分
    safe_filename = Path(file.filename).name
    local_file_path = str(local_dir_obj / safe_filename)
    with open(local_file_path, "wb") as f:
        shutil.copyfileobj(file.file, f,1024*1024)
    logger.info(f"文件上传成功，保存路径为：{local_file_path}")


    minio_client = get_minio_client()
    source_path = f"pdf_file/{date_str}/{task_id}/{safe_filename}"
    minio_client.fput_object(
        bucket_name=MinIoConfig.minio_bucket_name,
        object_name=source_path,
        file_path=local_file_path,
    )
    logger.info(f"文件上传成功，MinIO 对象路径为：{source_path}")

    # 文件已上传完成（本地 + minio），把「上传文件」节点标记为完成
    add_done_task(task_id, "upload_file")

    # 组装用户人工指定的元数据（非空字段才会在入库时覆盖自动识别结果）
    user_metadata = {
        "book_name": book_name.strip(),
        "author": author.strip(),
        "content_type": content_type.strip(),
        "category": category.strip(),
        "duration": duration.strip(),
    }

    background_tasks.add_task(
        run_main_graph,
        task_id=task_id,
        local_file_path=local_file_path,
        local_dir=local_dir,
        user_metadata=user_metadata,
        source_path=source_path,
    )

    # 主要返回task_id，防止报错，其他的数据要和前端页面核对，前端需要但是没有我们后端就要返回
    # 如果前端已经有相关的内容了，后端就可以不返
    return {"task_id": task_id,"file_size":file.size or 0,"file_name":safe_filename}

@app.get("/status/{task_id}")
async def get_status(task_id: str = fastapi.Path(...,description="任务ID")):
    return get_task_info(task_id)



if __name__ == '__main__':
    uvicorn.run(app,host="0.0.0.0",port=8000)

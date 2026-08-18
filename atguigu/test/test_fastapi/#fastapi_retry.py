import os.path
import shutil
import uuid

import uvicorn
from fastapi import Path, FastAPI, Query, UploadFile
from pydantic import Field, BaseModel
from starlette.responses import JSONResponse, FileResponse

app = FastAPI()

@app.get("/")
def index():
    return {"message":"你好呀"}

@app.get("/testpath/{id}/{name}/{gender}")
def testpath(id:int,name:str = Path(description="用户名"),gender:str = Path(description="性别")):
    return {"id":id,"name":name,"gender":gender}

@app.get("/testquery")
def testquery(
        id:int,
        height:float = 170,
        name:str = Query(...,description="姓名"),
        gender:str = Query(description="性别",default="female"),
):
    return {"id":id, "height":height, "name":name, "gender":gender}

class User(BaseModel):
    username: str = Field(title="用户名", description="用户名")
    age: int = Field(title="年龄", description="年龄",default=18)

@app.post("/testbody")
def testbody(user:User):
    return user

@app.post("/upload")
def upload(file:UploadFile):
    file_name=str(uuid.uuid4())[:8] + file.filename
    dir_path = "./"
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    fs = open(f"{dir_path}/{file_name}","wb")
    shutil.copyfileobj(file.file,fs, length=1024*1024)
    fs.close()
    return {"filename":file.filename}

@app.get("/api/user")
def get_user():
    return JSONResponse(
         content={
            "code":20000,
            "data":{
                "name": "张三",
                "age": 20
            }
        },
        status_code=200,  # 可选，默认 200
        headers={"xxx": "custom-value"}  # 可选，自定义响应头
    )

@app.get("/download")
def download():
    return FileResponse(
        path="D:/1#pycharm_class_code/kb_0515/atguigu/test/test_fastapi/static/1677923055.327402.png",
        filename="1677923055.327402.png",
        media_type="image/png"
    )














if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)

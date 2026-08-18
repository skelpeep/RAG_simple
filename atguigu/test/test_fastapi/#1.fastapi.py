import shutil
import uuid
from fastapi.responses import JSONResponse,HTMLResponse
from fastapi import FastAPI, Path, Query, Depends, Request, UploadFile, File, Body
import uvicorn
from pydantic import BaseModel, Field


app = FastAPI(
    title="FastAPI",
    description="A fast API for machine learning models",
    version="0.1.0",
)

@app.get("/")
def index():
    return {"message": "Hello World"}


# 带了路径参数就要写{xxxx},传递了必须占位
# Path里面 ...代表必须传递，default代表默认值 ,ge代表大于等于，le代表小于等于
@app.get("/testpath/{id}/{name}/{age}")
def testpath(
        id: int,
        name: str="nihao",  #但是路径参数必须传递，写了默认值也没什么意义
        age: int = Path(...,description="年龄",ge=0,le=120)
):
    return {"id":f"{id}", "name":f"{name}", "age":f"{age}"}

@app.get("/testquery")
def testquery(
        id: int,
        height: float=180, #默认传递180，可传可不传
        gender: str= Query(...,description="性别"), #写了...代表必传
        name: str= Query(default="hachimi",description="姓名"),
):
    return {"id":f"{id}", "height":f"{height}", "gender":f"{gender}", "name":f"{name}"}

# 请求体参数是挑请求方式，get,delete一般不用
# 只有post和put才用请求体参数
# 请求体参数一般都是json 只要是json请求体参数，BaseModel就能解析
# 1。会实例化一个对象 2.校验传递的json和定义的类是否匹配 3.返回实例化对象


class User(BaseModel):
    username:str =Field(...,description="用户名")
    password:str = Field(default="111111",description="密码")

@app.post("/testbody")
def testbody(user:User):
    return user


# 4.接受混合参数 路径查询请求体一起传递（第一种）
# @app.post(path="/testmixed/{id}")
# def testmixed(
#         user: User,
#         id: int = Path(...,description="用户id"),
#         name: str = Query(..., description="姓名"),
#         age:int = Query(default=18,description="年龄")
# ):
#     return {"user":user, "id":id, "name":name, "age":age}


# 5.接受混合参数 路径查询请求体一起传递（第二种）
# 使用BaseModel类去解决请求体，使用普通类解决路径和查询参数
# 依赖注入给了一个Depends类，使用它传递一个
#进行自动注入
#普通类去解决

class Student:
    def __init__(self, id: int=None, name: str=None,age:int=18):
        self.id = id
        self.name = name
        self.age = age


@app.post("/testmixed/{id}")
def testmixed(
        user:User = Body(...,description="用户请求体信息"),
        student:Student = Depends(Student)
):
  return {"id":student.id, "name":student.name, "age":student.age,"user":user}

# 6.接收请求头的信息
@app.get("/testheader")
def testheader(request:Request):
    print(request.headers.get("token"))
    return {"message":"helloworld"}

#7.接受文件
# 接收formData数据，文件上传，文件上传是表单提交的一种方式
@app.post("/upload")
def upload(file:UploadFile=File(...,description="上传文件")):
    print(file.filename,file.size,file.content_type,file.file,file.headers)
    # 拿到文件之后需要把文件保存到磁盘然后转储到对象容器（minio)中
    dir_path = "./"
    file_name = str(uuid.uuid4()) + file.filename # 生成一个随机的字符串，确保文件名唯一
    fs = open(dir_path+"/"+file_name, "wb")
    shutil.copyfileobj(file.file, fs, length=1024*1024)
    fs.close()

    # 转储后拿到网络路径(minio的图片路径)
    return {"filename":file.filename}

@app.get("/custom")
async def custom_response():
    pass

@app.get("/api/user")
async def get_user():
    # 等价于直接 return {"name": "张三", "age": 20}（FastAPI 自动转 JSONResponse）
    return JSONResponse(
        content={"name": "张三", "age": 20},
        status_code=200,  # 可选，默认 200
        headers={"X-Custom-Header": "custom-value"}  # 可选，自定义响应头
    )

# 了解
@app.get("/hello")
async def hello(name: str = "游客"):
    html_content = f"""
    <html>
        <head>
            <title>你好</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>你好，{name}！</h1>
            <p>欢迎来到FastAPI</p>
            <img src="https://picsum.photos/200/300" alt="随机图片" />
            <div>测试</div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)






if __name__ == '__main__':
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )



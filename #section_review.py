a = 0 and 10
b = 1 and 10
c = 0 or 10
d = True or 10
print(a,b,c,d) # 0 10 10 True

# ctrl shift u 转大小写

"""
幂等性删除指的是：同一个删除请求执行一次或执行多次，最终结果都一样。
即使资源已被删，通常也应安全返回成功结果，例如 204 No Content，或者明确返回“资源不存在”的 404；
重点是重复调用不能导致额外副作用或报错异常。
"""

# 节点路由return多个需要加个列表

list.extend([1,2,3,4])  # extend会将列表拆开放入之前的列表，append会直接将一个列表当元素添加

"""
 http：前后端交互的协议
    报文：请求报文，响应报文
        行 头 空行 体
        1.请求路径
        2.参数
        3.相应数据
        4.请求方式
            get
            post
            put
            delete
        5.状态码
            100 200 300 400 500
            
        参数：
            路径 path
            查询 query
            请求体 body （json） 包含 (form-data->文件）
            
        返回值（响应）

启动fastapi
if __name__ == '__main__':
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
测试文档：http://localhost:8000/docs

@app.get("/testquery") 一定要写"/"

query参数：放在url后面，用?连接，多个用&连接，例如http://localhost:8000/testmixed/100?name=hachimi&age=20


"""

# strip



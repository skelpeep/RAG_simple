import uvicorn
from fastapi import FastAPI, Path, Body, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path as FilePath
from starlette.middleware.cors import CORSMiddleware

from atguigu.tool import milvus_admin_tool as admin_tool
from atguigu.tool.logger import logger

app = FastAPI(
    title="智能听书知识库 · 书籍后台管理与知识库管理接口",
    description="书籍主体管理、知识库切片管理、统计概览",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PAGE_DIR = FilePath(__file__).resolve().parent.parent / "page"

# 统一托管前端页面（admin / import / chat）
app.mount("/page", StaticFiles(directory=PAGE_DIR), name="page")


@app.get("/")
async def index():
    """后台管理页面入口。"""
    return FileResponse(PAGE_DIR / "admin.html")


@app.get("/health")
async def health():
    return {"ok": True}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """统一异常兜底：底层依赖（Milvus 等）异常时返回友好 JSON，避免裸 500。"""
    logger.error(f"管理接口异常 {request.method} {request.url.path} -> {exc}")
    return JSONResponse(status_code=200, content={"ok": False, "msg": f"操作失败：{exc}"})


# ==================== 统计概览 ====================

@app.get("/api/stats")
async def stats():
    return admin_tool.get_stats()


# ==================== 书籍管理 ====================

@app.get("/api/books")
async def list_books(
    keyword: str = Query("", description="关键词（匹配条目/书名/作者/类别/来源文件）"),
    content_type: str = Query("", description="内容类型过滤"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return admin_tool.list_books(keyword=keyword, content_type=content_type, limit=limit, offset=offset)


@app.get("/api/books/{book_id}")
async def get_book(book_id: int = Path(..., description="书籍主体ID")):
    book = admin_tool.get_book(book_id)
    if not book:
        return {"ok": False, "msg": "书籍不存在"}
    return {"ok": True, "book": book}


class BookUpdate(BaseModel):
    item_name: str = Field(..., description="条目名称")
    book_name: str = Field("", description="书名")
    author: str = Field("", description="作者名")
    content_type: str = Field("", description="内容类型")
    category: str = Field("", description="类别/标签")


@app.put("/api/books/{book_id}")
async def update_book(book_id: int = Path(...), body: BookUpdate = Body(...)):
    return admin_tool.update_book(book_id, body.model_dump())


@app.delete("/api/books/{book_id}")
async def delete_book(book_id: int = Path(...)):
    return admin_tool.delete_book(book_id)


# ==================== 知识库切片管理 ====================

@app.get("/api/chunks")
async def list_chunks(
    keyword: str = Query("", description="关键词（匹配条目/书名/标题/正文/作者）"),
    item_name: str = Query("", description="条目名称精确过滤"),
    book_name: str = Query("", description="书名精确过滤"),
    content_type: str = Query("", description="内容类型过滤"),
    file_title: str = Query("", description="来源文件名模糊过滤"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return admin_tool.list_chunks(
        keyword=keyword, item_name=item_name, book_name=book_name,
        content_type=content_type, file_title=file_title, limit=limit, offset=offset,
    )


@app.delete("/api/chunks/{chunk_id}")
async def delete_chunk(chunk_id: int = Path(...)):
    return admin_tool.delete_chunk(chunk_id)


class ChunksBatchDelete(BaseModel):
    item_name: str = Field("", description="条目名称")
    book_name: str = Field("", description="书名")
    content_type: str = Field("", description="内容类型")
    file_title: str = Field("", description="来源文件名")


@app.delete("/api/chunks")
async def delete_chunks_batch(body: ChunksBatchDelete = Body(...)):
    return admin_tool.delete_chunks_by_filter(
        item_name=body.item_name, book_name=body.book_name,
        content_type=body.content_type, file_title=body.file_title,
    )


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8002)

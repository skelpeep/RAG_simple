# atguigu/tool/milvus_admin_tool.py
# 书籍后台管理 / 知识库管理的 Milvus 查询与维护工具
#
# 数据源：
#   - item_name_collection：书籍/条目主体元数据（item_name/book_name/author/content_type/category/file_title）
#   - chunks_collection    ：知识库切片（含打标元数据 + 正文 + 向量）
#
# 说明：这里只做「标量字段」的查询与维护；向量字段仅在需要保真回写时才读取。

from atguigu.config.config import MilvusConfig
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client

# 内容类型枚举（与导入/元数据识别保持一致）
CONTENT_TYPES = [
    "有声书信息",
    "书籍简介",
    "作者介绍",
    "听书笔记",
    "推荐运营资料",
    "用户评论摘要",
    "常见问答",
]

# 书籍主体可编辑的标量字段（file_title 为来源文件名，一般不改，但允许查看）
BOOK_SCALAR_FIELDS = ["item_name", "book_name", "author", "content_type", "category", "file_title"]

# 切片列表输出字段（不含向量，避免返回超大 payload）
CHUNK_SCALAR_FIELDS = [
    "id", "item_name", "book_name", "author", "content_type", "category",
    "duration", "source_path", "file_title", "title", "content", "part",
]


def _escape(value: str) -> str:
    """转义 Milvus 过滤表达式中的字符串，避免引号/反斜杠破坏语法。"""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _load(collection: str):
    client = get_milvus_client()
    client.load_collection(collection)
    return client


def _count(collection: str, expr: str = "") -> int:
    client = _load(collection)
    res = client.query(collection, filter=expr or "", output_fields=["count(*)"])
    return res[0]["count(*)"] if res else 0


def _serialize_row(row):
    """把 Milvus 返回的行做一次类型归一化，保证可 JSON 序列化。"""
    out = dict(row)
    if "id" in out and out["id"] is not None:
        out["id"] = int(out["id"])
    if "part" in out and out["part"] is not None:
        out["part"] = int(out["part"])
    return out


def _safe_chunk_fields(collection: str) -> list:
    """动态探测切片集合可用字段，兼容旧集合缺少 source_path 字段的情况。"""
    client = _load(collection)
    try:
        desc = client.describe_collection(collection)
        names = {f.get("name") for f in (desc.get("fields") or [])}
    except Exception:
        names = set()
    if names and "source_path" not in names:
        return [f for f in CHUNK_SCALAR_FIELDS if f != "source_path"]
    return list(CHUNK_SCALAR_FIELDS)


# ==================== 书籍主体管理 ====================

def list_books(keyword: str = "", content_type: str = "", limit: int = 20, offset: int = 0):
    """分页查询书籍/条目主体列表。"""
    collection = MilvusConfig.item_name_collection
    conds = []
    if keyword:
        k = _escape(keyword)
        conds.append(
            f'(item_name like "%{k}%" or book_name like "%{k}%" '
            f'or author like "%{k}%" or category like "%{k}%" or file_title like "%{k}%")'
        )
    if content_type:
        conds.append(f'content_type == "{_escape(content_type)}"')
    expr = " and ".join(conds) if conds else ""

    client = _load(collection)
    total = _count(collection, expr)
    rows = client.query(
        collection, filter=expr, output_fields=BOOK_SCALAR_FIELDS + ["id"], limit=limit, offset=offset
    )
    return {"total": total, "items": [_serialize_row(r) for r in rows]}


def get_book(book_id: int):
    """查询单条书籍主体详情。"""
    collection = MilvusConfig.item_name_collection
    client = _load(collection)
    rows = client.query(collection, filter=f"id == {int(book_id)}", output_fields=BOOK_SCALAR_FIELDS + ["id"])
    if not rows:
        return None
    return _serialize_row(rows[0])


def _get_rows_with_vectors(collection: str, expr: str, fields: list, limit: int = 20000):
    """读取含向量字段的行（供 delete+insert 保真回写使用）。"""
    client = _load(collection)
    return client.query(collection, filter=expr, output_fields=fields, limit=limit)


def update_book(book_id: int, fields: dict):
    """更新书籍主体元数据，并同步更新 chunks 集合中同名主体的打标字段。

    采用「读原行(含向量) -> 删 -> 插」保真回写，避免重算向量。
    若切片同步失败，则降级为只更新主体并返回 warning，不影响主体更新。
    """
    book_col = MilvusConfig.item_name_collection
    chunk_col = MilvusConfig.chunks_collection
    client = _load(book_col)

    rows = _get_rows_with_vectors(
        book_col, f"id == {int(book_id)}",
        BOOK_SCALAR_FIELDS + ["id", "dense_vector", "sparse_vector"],
    )
    if not rows:
        return {"ok": False, "msg": "书籍不存在"}

    old = rows[0]
    old_item_name = old.get("item_name", "")

    new_item_name = str(fields.get("item_name") or old.get("item_name") or "").strip()
    new_row = {
        "item_name": new_item_name,
        "book_name": str(fields.get("book_name") if fields.get("book_name") is not None else old.get("book_name", "")).strip(),
        "author": str(fields.get("author") if fields.get("author") is not None else old.get("author", "")).strip(),
        "content_type": str(fields.get("content_type") if fields.get("content_type") is not None else old.get("content_type", "")).strip(),
        "category": str(fields.get("category") if fields.get("category") is not None else old.get("category", "")).strip(),
        "file_title": old.get("file_title", ""),
        "dense_vector": old.get("dense_vector"),
        "sparse_vector": old.get("sparse_vector"),
    }
    if not new_row["item_name"]:
        return {"ok": False, "msg": "条目名称不能为空"}

    # 1) 更新主体集合
    client.delete(book_col, ids=[int(book_id)])
    client.insert(book_col, data=[{k: v for k, v in new_row.items() if k != "id"}])

    # 2) 同步 chunks 集合（尽力而为）
    warning = None
    try:
        chunk_fields = _safe_chunk_fields(chunk_col) + ["dense_vector", "sparse_vector"]
        chunk_rows = _get_rows_with_vectors(
            chunk_col, f'item_name == "{_escape(old_item_name)}"',
            chunk_fields,
        )
        if chunk_rows:
            for r in chunk_rows:
                r["item_name"] = new_row["item_name"]
                r["book_name"] = new_row["book_name"]
                r["author"] = new_row["author"]
                r["content_type"] = new_row["content_type"]
                r["category"] = new_row["category"]
            ids = [int(r["id"]) for r in chunk_rows if r.get("id") is not None]
            if ids:
                client.delete(chunk_col, ids=ids)
            client.insert(chunk_col, data=[{k: v for k, v in r.items() if k != "id"} for r in chunk_rows])
    except Exception as e:
        logger.error(f"同步切片元数据失败（主体已更新）：{e}")
        warning = f"主体已更新，但关联切片元数据同步失败：{e}"

    return {"ok": True, "msg": "更新成功", "warning": warning, "book": new_row}


def delete_book(book_id: int):
    """删除书籍主体及其名下所有切片。"""
    book_col = MilvusConfig.item_name_collection
    chunk_col = MilvusConfig.chunks_collection
    client = _load(book_col)

    rows = client.query(book_col, filter=f"id == {int(book_id)}", output_fields=["item_name"])
    if not rows:
        return {"ok": False, "msg": "书籍不存在"}

    item_name = rows[0].get("item_name", "")
    client.delete(book_col, ids=[int(book_id)])

    deleted_chunks = 0
    if item_name:
        client.load_collection(chunk_col)
        deleted_chunks = _count(chunk_col, f'item_name == "{_escape(item_name)}"')
        client.delete(chunk_col, filter=f'item_name == "{_escape(item_name)}"')

    return {"ok": True, "msg": "删除成功", "deleted_chunks": deleted_chunks}


# ==================== 知识库切片管理 ====================

def list_chunks(
    keyword: str = "", item_name: str = "", book_name: str = "",
    content_type: str = "", file_title: str = "", limit: int = 20, offset: int = 0,
):
    """分页查询切片列表，支持多条件过滤。"""
    collection = MilvusConfig.chunks_collection
    conds = []
    if keyword:
        k = _escape(keyword)
        conds.append(
            f'(item_name like "%{k}%" or book_name like "%{k}%" or title like "%{k}%" '
            f'or content like "%{k}%" or author like "%{k}%")'
        )
    if item_name:
        conds.append(f'item_name == "{_escape(item_name)}"')
    if book_name:
        conds.append(f'book_name == "{_escape(book_name)}"')
    if content_type:
        conds.append(f'content_type == "{_escape(content_type)}"')
    if file_title:
        conds.append(f'file_title like "%{_escape(file_title)}%"')
    expr = " and ".join(conds) if conds else ""

    client = _load(collection)
    total = _count(collection, expr)
    fields = _safe_chunk_fields(collection)
    rows = client.query(collection, filter=expr, output_fields=fields, limit=limit, offset=offset)
    return {"total": total, "items": [_serialize_row(r) for r in rows]}


def delete_chunk(chunk_id: int):
    """删除单条切片。"""
    collection = MilvusConfig.chunks_collection
    client = _load(collection)
    client.delete(collection, ids=[int(chunk_id)])
    return {"ok": True, "msg": "删除成功"}


def delete_chunks_by_filter(item_name: str = "", book_name: str = "", content_type: str = "", file_title: str = ""):
    """按过滤条件批量删除切片。无任何条件时拒绝执行，防止误删全库。"""
    collection = MilvusConfig.chunks_collection
    conds = []
    if item_name:
        conds.append(f'item_name == "{_escape(item_name)}"')
    if book_name:
        conds.append(f'book_name == "{_escape(book_name)}"')
    if content_type:
        conds.append(f'content_type == "{_escape(content_type)}"')
    if file_title:
        conds.append(f'file_title like "%{_escape(file_title)}%"')
    if not conds:
        return {"ok": False, "msg": "拒绝执行：请至少提供一个过滤条件，避免误删全库"}

    expr = " and ".join(conds)
    client = _load(collection)
    deleted = _count(collection, expr)
    client.delete(collection, filter=expr)
    return {"ok": True, "msg": "删除成功", "deleted": deleted}


# ==================== 统计概览 ====================

def get_stats():
    """知识库统计概览：书籍/切片总数 + 内容类型分布。"""
    book_col = MilvusConfig.item_name_collection
    chunk_col = MilvusConfig.chunks_collection

    total_books = _count(book_col)
    total_chunks = _count(chunk_col)

    content_type_dist = {}
    for ct in CONTENT_TYPES:
        n = _count(chunk_col, f'content_type == "{_escape(ct)}"')
        if n > 0:
            content_type_dist[ct] = n
    # 未识别/空类型归入「未分类」
    uncategorized = _count(chunk_col, 'content_type == "" or content_type is null')
    if uncategorized > 0:
        content_type_dist["未分类"] = uncategorized

    return {
        "total_books": total_books,
        "total_chunks": total_chunks,
        "content_type_dist": content_type_dist,
    }

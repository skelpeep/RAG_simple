# atguigu/import_process/nodes/node_cover_embedding.py
"""
封面向量化入库节点：封面图片 + 封面描述文本 -> 多模态向量 -> 封面集合（Milvus）。

位置：在「主体元数据识别」之后、「正文向量化」之前运行（需要 item_name/book_name 等元数据）。

封面来源优先级：
  1. state["cover_image_path"]：导入时前端显式上传的封面图片本地路径；
  2. 自动探测：Markdown 同级 images/ 目录中，优先匹配文件名含 cover/封面 的图片，
     否则取第一张图片。

说明：封面为可选能力——找不到封面或多模态向量未配置时降级跳过，不阻断主流程。
"""
from pathlib import Path

from pymilvus import DataType

from atguigu.config.config import MinIoConfig, MilvusConfig, MultimodalConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client
from atguigu.tool.minio_client_tool import get_minio_client
from atguigu.tool.multimodal_embedding_tool import embed_multimodal_images, embed_multimodal_text

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


class NodeCoverEmbedding(NodeBase):
    """封面图片与封面描述联合向量化，写入 Milvus 封面集合。"""

    name = "node_cover_embedding"

    def find_cover_image(self, state: ImportGraphState) -> str:
        """确定封面图片本地路径（显式上传 > 自动探测）。"""
        cover = (state.get("cover_image_path") or "").strip()
        if cover and Path(cover).exists():
            return cover

        md_path = state.get("md_path") or ""
        if not md_path:
            return ""
        images_dir = Path(md_path).parent / "images"
        if not images_dir.exists():
            return ""
        imgs = sorted(
            [p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS],
            key=lambda p: p.name,
        )
        if not imgs:
            return ""
        for p in imgs:
            if "cover" in p.stem.lower() or "封面" in p.stem:
                return str(p)
        return str(imgs[0])

    def build_cover_desc(self, state: ImportGraphState) -> str:
        """用主体元数据拼一段封面描述文本，作为 text_vector 的输入（文搜图用）。"""
        metadata = state.get("book_metadata") or {}
        item_name = state.get("item_name") or metadata.get("item_name") or ""
        parts = [
            item_name,
            metadata.get("book_name") or "",
            metadata.get("author") or "",
            metadata.get("category") or "",
            metadata.get("content_type") or "",
        ]
        return " ".join(p for p in parts if p).strip()

    def upload_cover(self, cover_path: str, file_title: str) -> str:
        """上传封面到 MinIO，返回可访问 URL。"""
        minio_client = get_minio_client()
        cover_dir = MinIoConfig.minio_cover_dir
        file_name = Path(cover_path).name
        object_name = f"{cover_dir}/{file_title}/{file_name}"
        minio_client.fput_object(
            bucket_name=MinIoConfig.minio_bucket_name,
            object_name=object_name,
            file_path=cover_path,
        )
        url = (
            f"http://{MinIoConfig.minio_endpoint}/{MinIoConfig.minio_bucket_name}/{object_name}"
        )
        return url

    def create_cover_collection(self):
        """创建封面集合（不存在时）。字段含 image_vector 与 text_vector 两个多模态向量。"""
        milvus_client = get_milvus_client()
        collection_name = MilvusConfig.cover_collection
        dim = MultimodalConfig.mm_embedding_dim
        if not milvus_client.has_collection(collection_name):
            schema = milvus_client.create_schema(auto_id=True)
            schema.add_field(
                field_name="id", datatype=DataType.INT64, is_primary=True
            ).add_field(
                field_name="item_name", datatype=DataType.VARCHAR, max_length=100
            ).add_field(
                field_name="book_name", datatype=DataType.VARCHAR, max_length=200
            ).add_field(
                field_name="author", datatype=DataType.VARCHAR, max_length=100
            ).add_field(
                field_name="content_type", datatype=DataType.VARCHAR, max_length=50
            ).add_field(
                field_name="category", datatype=DataType.VARCHAR, max_length=200
            ).add_field(
                field_name="file_title", datatype=DataType.VARCHAR, max_length=100
            ).add_field(
                field_name="cover_url", datatype=DataType.VARCHAR, max_length=500
            ).add_field(
                field_name="cover_desc", datatype=DataType.VARCHAR, max_length=1000
            ).add_field(
                field_name="image_vector", datatype=DataType.FLOAT_VECTOR, dim=dim
            ).add_field(
                field_name="text_vector", datatype=DataType.FLOAT_VECTOR, dim=dim
            )

            index_params = milvus_client.prepare_index_params()
            for field_name in ("image_vector", "text_vector"):
                index_params.add_index(
                    field_name=field_name,
                    index_type="IVF_FLAT",
                    metric_type="COSINE",
                    params={"nlist": 128, "nprobe": 16},
                )

            milvus_client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params,
            )
        return collection_name, milvus_client

    def process(self, state: ImportGraphState):
        cover_path = self.find_cover_image(state)
        if not cover_path:
            logger.info("未找到封面图片，跳过多模态封面入库")
            return {}

        cover_desc = self.build_cover_desc(state)
        if not cover_desc:
            cover_desc = state.get("item_name") or state.get("file_title") or ""

        metadata = state.get("book_metadata") or {}
        item_name = state.get("item_name") or metadata.get("item_name") or ""
        file_title = state.get("file_title") or ""

        try:
            image_vector = embed_multimodal_images([cover_path])[0]
            text_vector = embed_multimodal_text([cover_desc])[0]
        except Exception as e:
            # 多模态向量未配置/调用失败时降级跳过，不阻断主流程
            logger.warning(f"封面向量化失败（跳过封面入库）：{e}")
            return {}

        cover_url = self.upload_cover(cover_path, file_title)

        collection_name, milvus_client = self.create_cover_collection()
        milvus_client.load_collection(collection_name=collection_name)

        # 同一主体重复导入时，先删旧封面再插新封面，避免重复
        safe_item_name = item_name.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        filter_str = f"item_name == '{safe_item_name}'"
        milvus_client.delete(collection_name=collection_name, filter=filter_str)

        data = {
            "item_name": item_name,
            "book_name": metadata.get("book_name", ""),
            "author": metadata.get("author", ""),
            "content_type": metadata.get("content_type", ""),
            "category": metadata.get("category", ""),
            "file_title": file_title,
            "cover_url": cover_url,
            "cover_desc": cover_desc,
            "image_vector": image_vector,
            "text_vector": text_vector,
        }
        milvus_client.insert(collection_name=collection_name, data=[data])
        logger.info(f"封面入库成功：{item_name} -> {cover_url}")

        return {"cover_url": cover_url}


if __name__ == "__main__":
    node = NodeCoverEmbedding()
    init_state = {
        "md_path": r"D:\1neiwangtong\output\hak180产品安全手册\hak180产品安全手册_new.md",
        "file_title": "hak180产品安全手册",
        "item_name": "BrotherHAK180烫金机",
        "book_metadata": {
            "book_name": "HAK180烫金机产品安全手册",
            "author": "Brother",
            "content_type": "常见问答",
            "category": "设备手册",
            "duration": "",
        },
    }
    result = node(init_state)
    logger.info(json_format(result))

# atguigu/query_process/nodes/node_search_cover.py
"""
封面检索节点：多模态封面检索（图搜图 + 文搜图）。

- 若 state 中存在 query_image（用户上传的封面图），用图片向量检索 image_vector（图搜图）；
- 同时用改写后的问题文本检索 text_vector（文搜图，跨模态）。

检索结果映射为与正文切片兼容的结构（source=cover），进入 RRF 融合，实现封面+内容联合检索。
多模态向量未配置或调用失败时降级为空结果，不阻断查询主链路。
"""
import json

from atguigu.config.config import MilvusConfig
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import search_dense
from atguigu.tool.multimodal_embedding_tool import embed_multimodal_images, embed_multimodal_text

COVER_OUTPUT_FIELDS = [
    "id", "item_name", "book_name", "author", "content_type",
    "category", "file_title", "cover_url", "cover_desc",
]


class NodeSearchCover(NodeBase):
    """节点功能：基于多模态向量的封面检索（图片搜图 / 文本搜图）。"""

    name: str = "node_search_cover"

    def _to_cover_chunk(self, hit) -> dict:
        entity = hit.get("entity", {}) or {}
        return {
            # 使用字符串 id，避免与正文切片的整型 id 在 RRF 字典中冲突
            "id": f"cover_{entity.get('id')}",
            "title": entity.get("item_name") or entity.get("book_name") or "封面",
            "content": entity.get("cover_desc") or "",
            "url": entity.get("cover_url") or "",
            "source": "cover",
            "item_name": entity.get("item_name") or "",
            "book_name": entity.get("book_name") or "",
            "author": entity.get("author") or "",
            "content_type": entity.get("content_type") or "",
            "category": entity.get("category") or "",
            "file_title": entity.get("file_title") or "",
            "score": hit.get("distance", 0.0),
        }

    def search_by_image(self, query_image, limit=5):
        vector = embed_multimodal_images([query_image])[0]
        res = search_dense(
            collection_name=MilvusConfig.cover_collection,
            vector=vector,
            anns_field="image_vector",
            limit=limit,
            output_fields=COVER_OUTPUT_FIELDS,
        )
        return res[0] if res else []

    def search_by_text(self, query_text, limit=5):
        vector = embed_multimodal_text([query_text])[0]
        res = search_dense(
            collection_name=MilvusConfig.cover_collection,
            vector=vector,
            anns_field="text_vector",
            limit=limit,
            output_fields=COVER_OUTPUT_FIELDS,
        )
        return res[0] if res else []

    def process(self, state: QueryGraphState):
        query_image = (state.get("query_image") or "").strip()
        rewritten_query = (state.get("rewritten_query") or "").strip()

        cover_chunks = []
        seen_ids = set()
        try:
            # 图片搜图（用户上传了封面图时）
            if query_image:
                for hit in self.search_by_image(query_image):
                    chunk = self._to_cover_chunk(hit)
                    if chunk["id"] not in seen_ids:
                        seen_ids.add(chunk["id"])
                        cover_chunks.append(chunk)

            # 文搜图（跨模态：用问题文本找对应封面）
            if rewritten_query:
                for hit in self.search_by_text(rewritten_query):
                    chunk = self._to_cover_chunk(hit)
                    if chunk["id"] not in seen_ids:
                        seen_ids.add(chunk["id"])
                        cover_chunks.append(chunk)
        except Exception as e:
            # 多模态向量未配置/失败时降级，不影响正文检索主链路
            logger.warning(f"封面检索失败（降级为空结果）：{e}")
            cover_chunks = []

        return {"cover_chunks": cover_chunks}


if __name__ == "__main__":
    init_state = {
        "rewritten_query": "关于BrotherHAK180烫金机如何使用",
        "query_image": "",
    }
    node_search_cover = NodeSearchCover()
    result = node_search_cover(init_state)
    logger.info(json_format(result))

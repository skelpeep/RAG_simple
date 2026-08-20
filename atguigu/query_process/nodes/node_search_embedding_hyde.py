# atguigu/query_process/nodes/node_search_embedding_hyde.py
import json

from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig, MilvusConfig
from atguigu.config.prompt import HYDE_PROMPT
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, search_hybrid


class NodeSearchEmbeddingHyde(NodeBase):
    """
    节点功能：HyDE (Hypothetical Document Embedding)
    先让 LLM 生成假设性答案，再对答案进行向量检索，提高召回率。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_search_embedding_hyde"

    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """
        rewritten_query = state.get("rewritten_query")
        item_names = state.get("item_names")
        if not rewritten_query:
            logger.error("rewritten_query 为空")
            raise ValueError("rewritten_query 为空")

        if not item_names:
            logger.error("item_names 为空")
            raise ValueError("item_names 为空")

        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url = LLMConfig.openai_api_base,
            temperature=LLMConfig.llm_default_temperature
        )

        messages = [
            {"role": "user","content":HYDE_PROMPT.format(rewritten_query=rewritten_query)}
                    ]
        res = llm.invoke(input=messages)
        hyde_answer = res.content
        merged_query = f"{rewritten_query} {hyde_answer}"

        embeddings = get_bge_m3_embedding([merged_query])
        collection_name = MilvusConfig.chunks_collection
        dense_data = embeddings.get("dense")[0]
        sparse_data = embeddings.get("sparse")[0]

        # item_names = [
        #     item.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        #     for item in item_names
        # ]

        expr = f"item_name in {json.dumps(item_names,ensure_ascii=False)}"

        reqs = create_reqs(
            dense_data=dense_data,
            sparse_data=sparse_data,
            dense_anns_field="dense_vector",
            sparse_anns_field="sparse_vector",
            expr=expr
        )

        res = search_hybrid(
            collection_name=collection_name,
            reqs=reqs,
            ranker=(0.8, 0.2),
            output_fields=["id", "title", "file_title", "content", "item_name", "book_name", "author", "content_type", "category", "duration"],
            limit=10
        )

        hyde_embedding_chunks = [
            {
                **item.get("entity", {}),
                "score": item.get("distance"),
                "source": "local"
            }
            for item in res[0]
        ]

        return {"hyde_embedding_chunks":hyde_embedding_chunks}




if __name__ == "__main__":
    init_state = {
        "rewritten_query": "关于BrotherHAK180烫金机如何使用",
        "item_names": ["BrotherHAK180烫金机"]
    }
    node_search_embedding_hyde = NodeSearchEmbeddingHyde()
    result = node_search_embedding_hyde(init_state)
    logger.info(json_format(result))

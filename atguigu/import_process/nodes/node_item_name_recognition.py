# atguigu/import_process/nodes/node_item_name_recognition.py
import json

from langchain.chat_models import init_chat_model
from pymilvus import DataType

from atguigu.config.config import LLMConfig, MilvusConfig
from atguigu.config.prompt import ITEM_NAME_SYSTEM_PROMPT, ITEM_NAME_USER_PROMPT_TEMPLATE
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import  get_milvus_client


class NodeItemNameRecognition(NodeBase):
    """
    主体识别节点：主体识别与标签提取
    """

    name = "node_item_name_recognition"

    def get_chunks(self, state):
        chunks = state.get("chunks")
        file_title = state.get("file_title")
        if not chunks:
            logger.error("chunks为空")
            raise Exception("chunks为空")

        if not file_title:
            logger.error("file_title为空")
            raise Exception("file_title为空")
        return chunks, file_title

    def get_chunk_content(self, chunks, file_title):
        # 根据chunks让大模型识别主体
        # 截取k个chunk,防止内容加起来超过token限制
        chunk_k_list = chunks[:10]
        max_len = 10000
        content_str = "\n"
        for idx, chunk in enumerate(chunk_k_list, start=1):
            title = chunk.get("title")
            content = chunk.get("content")
            chunk_str = f"[切片{idx}]\n{file_title}\n{title}\n{content}\n"
            if len(content_str) > max_len:
                logger.info(f"已经超过最大长度，不拼接")
                break
            content_str += chunk_str

        content_str = content_str[:max_len]
        return content_str

    def get_item_name(self, content_str, file_title):
        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_api_base,
            temperature=LLMConfig.llm_default_temperature
        )

        messages = [
            {"role": "system", "content": ITEM_NAME_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": ITEM_NAME_USER_PROMPT_TEMPLATE.format(file_title=file_title, context=content_str)
            }
        ]

        res = llm.invoke(input=messages)
        item_name = res.content
        item_name = item_name.replace(" ", "").replace("\t", "").replace("\n", "")

        if not item_name:
            item_name = file_title
        return item_name

    def create_milvus_collection(self):
        milvus_client = get_milvus_client()
        if not milvus_client:
            logger.error("初始化milvus_client失败")
            raise Exception("初始化milvus_client失败")

        collection_name = MilvusConfig.item_name_collection
        if not milvus_client.has_collection(collection_name):
            schema = milvus_client.create_schema(
                auto_id=True
            )
            schema.add_field(
                field_name="id",
                datatype=DataType.INT64,
                is_primary=True,
            ).add_field(
                field_name="item_name",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="file_title",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="dense_vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=1024
            ).add_field(
                field_name="sparse_vector",
                datatype=DataType.SPARSE_FLOAT_VECTOR
            )

            index_params = milvus_client.prepare_index_params()
            index_params.add_index(
                field_name="dense_vector",
                index_type="IVF_FLAT",  # 暴力检索
                metric_type="COSINE",
                params={"nlist": 128, "nprobe": 16}  # 提升效率否则暴力检索效率太低
            )

            index_params.add_index(
                field_name="sparse_vector",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP",
                params={
                    "inverted_index_algo": "DAAT_MAXSCORE",
                    # 高效的稀疏检索算法
                    "normalize": True,
                    # ↑ L2 归一化，让内积 (IP) 等价于余弦相似度
                    "quantization": "none"
                    # ↑ 关闭量化，保持原始精度：模型生成的向量已经压缩的一半的精度了（BGE_FP16=1），这里就不再压缩了
                    # "quantization": "none" → 存储原始向量，不压缩
                    # "quantization": "sq8" → 存储压缩后的向量（8-bit 量化
                }
            )

            milvus_client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params
            )
        return collection_name, milvus_client

    def insert_data_backup(self, chunks, collection_name, file_title, item_name, milvus_client):
        milvus_client.load_collection(collection_name=collection_name)
        safe_item_name = item_name.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        filter_str = f"item_name == '{safe_item_name}'"
        milvus_client.delete(collection_name=collection_name, filter=filter_str)
        embedding = get_bge_m3_embedding([item_name])

        data = {
            "item_name": item_name,
            "file_title": file_title,
            "dense_vector": embedding.get("dense")[0],
            "sparse_vector": embedding.get("sparse")[0]
        }

        milvus_client.insert(collection_name=collection_name, data=[data])

        for chunk in chunks:
            chunk["item_name"] = item_name


    def process(self, state: ImportGraphState):
        chunks, file_title = self.get_chunks(state)

        content_str = self.get_chunk_content(chunks, file_title)
        item_name = self.get_item_name(content_str, file_title)

        collection_name, milvus_client = self.create_milvus_collection()

        self.insert_data_backup(chunks, collection_name, file_title, item_name, milvus_client)

        return {
            "item_name":item_name,
            "chunks":chunks
        }



if __name__ == '__main__':
    node = NodeItemNameRecognition()
    with open(r"D:\1neiwangtong\output\hak180产品安全手册\chunks.json","r",encoding="utf-8") as f:
        chunks = json.load(f)

    init_state = {
        "file_title": "hak180产品安全手册",
        "chunks": chunks,
    }
    res =node(init_state)
    logger.info(json_format(res))
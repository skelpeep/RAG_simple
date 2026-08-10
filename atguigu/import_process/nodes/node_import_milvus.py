# atguigu/import_process/nodes/node_import_milvus.py
import json

from pymilvus import DataType

from atguigu.config.config import MilvusConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client


class NodeImportMilvus(NodeBase):
    """
    导入向量库节点：数据持久化
    """

    name = "node_import_milvus"

    def get_chunks(self, state):
        chunks = state.get("chunks", "")
        if not chunks:
            logger.error("未找到chunks")
            raise Exception("未找到chunks")
        dense_dim = len(chunks[0].get("dense_vector"))
        file_title = chunks[0].get("file_title")
        return chunks, dense_dim, file_title

    def create_milvus_collection(self, dense_dim):
        milvus_client = get_milvus_client()
        collection_name = MilvusConfig.chunks_collection
        if not milvus_client:
            logger.error("milvus_client初始化失败")
            raise Exception("milvus_client初始化失败")

        if not milvus_client.has_collection(collection_name):
            schema = milvus_client.create_schema(auto_id=True)
            schema.add_field(
                field_name="id",
                datatype=DataType.INT64,
                is_primary=True
            ).add_field(
                field_name="file_title",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="title",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="content",
                datatype=DataType.VARCHAR,
                max_length=5000
            ).add_field(
                field_name="item_name",
                datatype=DataType.VARCHAR,
                max_length=100
            ).add_field(
                field_name="part",
                datatype=DataType.INT64
            ).add_field(
                field_name="dense_vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=dense_dim
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

    def insert_data(self, chunks, collection_name, file_title, milvus_client):
        milvus_client.load_collection(collection_name=collection_name)
        file_title = file_title.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        filter_str = f"file_title == '{file_title}'"
        milvus_client.delete(collection_name=collection_name, filter=filter_str)
        res = milvus_client.insert(collection_name=collection_name, data=chunks)
        logger.info(res)
        ids = res.get("ids")
        if ids:
            for i, chunk in enumerate(chunks):
                chunk["id"] = ids[i]



    def process(self, state: ImportGraphState):
        chunks, dense_dim, file_title = self.get_chunks(state)

        collection_name, milvus_client = self.create_milvus_collection(dense_dim)

        self.insert_data(chunks, collection_name, file_title, milvus_client)

        return {
            "chunks":chunks
        }



if __name__ == '__main__':
    node = NodeImportMilvus()
    with open(r"D:\1neiwangtong\output\hak180产品安全手册\embedding_chunks.json","r",encoding="utf=8") as f:
        chunks = json.load(f)
    init_state ={
        "chunks":chunks
    }
    result = node(init_state)
    logger.info(json_format(result))







import threading
from typing import List

from pymilvus.model.hybrid import BGEM3EmbeddingFunction

from atguigu.config.config import EmbeddingConfig
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger


bge_m3_model = None
# 可重入锁：BGE-M3 是懒加载单例，查询链路里 node_search_embedding 与 node_search_embedding_hyde
# 并行、冷启动时同时触发首次加载，无锁会导致 meta tensor 竞态（Cannot copy out of meta tensor）
_bge_m3_lock = threading.RLock()


def get_bge_m3_model():
    global bge_m3_model
    if not bge_m3_model:
        with _bge_m3_lock:
            if not bge_m3_model:
                bge_m3_model = BGEM3EmbeddingFunction(
                    model_name=EmbeddingConfig.bge_m3_path,
                    device=EmbeddingConfig.bge_device,
                    use_fp16=EmbeddingConfig.bge_fp16
                )
    return bge_m3_model

def get_bge_m3_embedding(texts:List[str]):
    # 全程串行（RLock 可重入）：模型加载 + 首次 encode 的 .to(device) 均有并发竞态风险
    with _bge_m3_lock:
        bge_m3_model = get_bge_m3_model()
        embedding = bge_m3_model.encode_documents(texts)

    # for dense_item in embedding.get('dense'):
    #     print(dense_item,type(dense_item))
    # return {
    #     "dense": [list(dense_item) for dense_item in embedding.get("dense")],
    #     "sparse": [
    #         {int(index): float(value) for index, value in zip(sparse_item.indices, sparse_item.data)}
    #         for sparse_item in embedding.get("sparse")
    #     ]
    # }

    return {
        "dense": [list(dense_item) for dense_item in embedding.get("dense")],
        "sparse": [dict(zip(sparse_item.indices.tolist(),sparse_item.data.tolist() )) for sparse_item in embedding.get('sparse')]
    }

if __name__ == '__main__':
    texts = ["hello world","hello milvus"]
    result = get_bge_m3_embedding(texts)
    logger.info(json_format(result))

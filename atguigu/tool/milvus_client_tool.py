

from pymilvus import MilvusClient, AnnSearchRequest, WeightedRanker

from atguigu.config.config import MilvusConfig

milvus_client = None
def get_milvus_client():
    global milvus_client
    if not milvus_client:
        milvus_client = MilvusClient(uri=MilvusConfig.milvus_url)
    return  milvus_client



def create_reqs(dense_data, sparse_data,dense_anns_field=None,sparse_anns_field=None,limit=10,dense_param=None,sparse_param=None,expr=None):
    if not dense_param:
        dense_param={
            "metric_type": "COSINE",
        }
    if not sparse_param:
        sparse_param={
            "metric_type": "IP",
        }


    dense_req=AnnSearchRequest(
        data=[dense_data],
        anns_field=dense_anns_field,
        param=dense_param,
        limit=limit,
        expr=expr
    )
    sparse_req =AnnSearchRequest(
        data=[sparse_data],
        anns_field=sparse_anns_field,
        param=sparse_param,
        limit=limit,
        expr=expr
    )
    return [dense_req, sparse_req]

def search_hybrid(collection_name,reqs,ranker=(0.5,0.5),limit=10,output_fields=None):  # ranker的俩表示dense和sparse的权重占比
    milvus_client = get_milvus_client()

    # 自己分配权重
    weight_ranker =WeightedRanker(ranker[0],ranker[1],norm_score=True)

    res =milvus_client.hybrid_search(
        collection_name=collection_name,
        reqs= reqs,
        ranker=weight_ranker,
        limit=limit,
        output_fields=output_fields
    )

    return res


def search_dense(collection_name, vector, anns_field, limit=10, output_fields=None, expr=None, metric_type="COSINE"):
    """单向量（稠密）检索，用于多模态封面检索（图搜图 / 文搜图）。"""
    milvus_client = get_milvus_client()
    milvus_client.load_collection(collection_name=collection_name)
    search_params = {"metric_type": metric_type, "params": {"nprobe": 16}}
    res = milvus_client.search(
        collection_name=collection_name,
        data=[vector],
        anns_field=anns_field,
        limit=limit,
        output_fields=output_fields,
        search_params=search_params,
        # 注意：MilvusClient.search 的过滤参数名是 filter，不是 expr
        filter=expr,
    )
    return res








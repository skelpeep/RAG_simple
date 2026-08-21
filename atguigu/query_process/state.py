# atguigu/query_process/state.py
from queue import Queue
from typing import TypedDict, List

class QueryGraphState(TypedDict):
    """
    查询流程图状态
    包含整个查询流程中传递的所有数据。
    """
    task_id: str # 任务ID
    session_id: str  # 会话ID
    message_id: str  # 消息ID
    q :Queue
    original_query: str  # 用户原始问题
    query_image: str  # 用户上传的封面图片（本地路径 / URL / base64），用于多模态封面检索（可选）

    # 检索过程中的中间数据
    embedding_chunks: list  # 普通向量检索回来的切片
    hyde_embedding_chunks: list  # 已向量化的假设性问题切片
    cover_chunks: list  # 多模态封面检索回来的封面切片
    web_search_docs: list  # 网络搜索回来的文档

    # 排序过程中的数据
    rrf_chunks: list  # RRF 融合排序后的切片
    reranked_docs: list  # 重排序后的最终 Top-K 文档

    # 生成过程中的数据
    prompt: str  # 组装好的 Prompt
    answer: str  # 最终生成的答案

    # 辅助信息
    item_names: List[str]  # 提取出的书籍/作者/类别/场景主体（如 刘慈欣《三体》、科幻有声书）
    rewritten_query: str  # 改写后的问题
    is_topic_search: bool  # 是否为类别/场景/主题类检索（未匹配到具体书籍主体，走无 item_name 过滤的向量检索）
    history: list  # 历史对话记录
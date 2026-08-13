
import json

from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig, MilvusConfig
from atguigu.config.prompt import ITEM_NAME_EXTRACT_SYSTEM_PROMPT, ITEM_NAME_EXTRACT_TEMPLATE
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, search_hybrid
from atguigu.tool.mongo_client_tool import add_or_update_history, get_recent_history_list, update_item_names_and_query


class NodeItemNameConfirm(NodeBase):
    """
    节点功能：确认用户问题中的核心商品名称。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_item_name_confirm"

    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """
        session_id = state.get("session_id")
        original_query = state.get('original_query')
        if not session_id:
            logger.error("会话ID不存在")
            raise ValueError("会话ID不存在")
        if not original_query:
            logger.error("原始查询不存在")
            raise ValueError("原始查询不存在")
        message_id = add_or_update_history(session_id, "user", original_query)
        history_list =get_recent_history_list(session_id)
        history_content = ""
        for history in history_list:
            text = history.get("text")
            role = history.get("role")
            content = f"{role}: {text}\n"
            history_content += content

        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_api_base,
            temperature=LLMConfig.llm_default_temperature
        )

        messages = [{"role": "system", "content": ITEM_NAME_EXTRACT_SYSTEM_PROMPT},
                    {"role": "user", "content": ITEM_NAME_EXTRACT_TEMPLATE.format(history_text=history_content, original_query=original_query)}]

        res = llm.invoke(messages)
        res_json = res.content
        if res_json.startswith("```json"):
            res_json = res_json.replace("```json", "").replace("```", "")
        res_dict = json.loads(res_json)
        item_names = res_dict.get("item_names")
        rewritten_query = res_dict.get("rewritten_query")
        if item_names:
            item_names = [
                item_name.replace(" ", "").replace("\n", "").replace("\t", "")
                for item_name in item_names
            ]
        else:
            item_names = []
        if not rewritten_query:
            rewritten_query = original_query

        answer = ""
        final_item_names = []
        if item_names:
            embeddings = get_bge_m3_embedding(item_names)
            collection_name = MilvusConfig.item_name_collection
            final_search_item_names = []
            for idx, item_name in enumerate(item_names):
                dense_data = embeddings.get("dense")[idx]
                sparse_data = embeddings.get("sparse")[idx]

                reqs = create_reqs(
                    dense_data=dense_data,
                    sparse_data=sparse_data,
                    dense_anns_field="dense_vector",
                    sparse_anns_field="sparse_vector"
                )

                res = search_hybrid(
                    collection_name=collection_name,
                    reqs=reqs,
                    ranker=(0.8, 0.2),
                    limit=10,
                    output_fields=["item_name"]
                )

                print(json_format(res))
                print(res[0])

                search_item_names = [
                    {
                        "original_item_name": item_name,
                        "search_item_name": item.get("entity",{}).get("item_name",""),
                        "score": item.get('distance')
                    }
                    for item in res[0]
                ]
                final_search_item_names.extend(search_item_names)

                confirm_item_names =[
                    item.get("search_item_name")
                    for item in final_search_item_names
                    if item.get("score") >= 0.85
                ]
                option_item_names = [
                    item.get("search_item_name")
                    for item in final_search_item_names
                    if 0.6 <= item.get("score") < 0.85
                ]

                if confirm_item_names:
                    final_item_names = confirm_item_names
                    answer = ""
                elif option_item_names:
                    final_item_names = confirm_item_names
                    answer = f"请确认你要咨询的商品是这些的哪一个？{",".join(option_item_names)}"
                else:
                    final_item_names = []
                    answer =f"对不起，我无法识别你要咨询的商品名称,请重新提问。"

        if answer:
            message_id = add_or_update_history(session_id, "assistant", answer)
        history_list = get_recent_history_list(session_id,limit=10)
        ids = [history.get("_id") for history in history_list]
        if ids:
            update_item_names_and_query(ids,final_item_names,rewritten_query)
        return {
            "message_id": message_id,
            "original_query": original_query,
            "answer": answer,
            "item_names": final_item_names,
            "rewritten_query": rewritten_query,
            "history": get_recent_history_list(session_id, limit=10)
        }








if __name__ == "__main__":

    # 模拟会话历史
    session_id = "test_001"
    # add_or_update_history(session_id, "user", "咨询下烫金机。")
    # add_or_update_history(session_id, "assistant", "您好。请问是哪个型号")
    # add_or_update_history(session_id, "user", "hak180")
    # add_or_update_history(session_id, "assistant", "具体有什么问题呢？")

    # 初始化图状态
    init_state = {
        "session_id": "test_001",
        "original_query": "咋用？"
    }

    # 创建节点对象
    node_item_name_confirm = NodeItemNameConfirm()
    # 执行节点的单元测试
    result = node_item_name_confirm(init_state)
    # 将返回的图状态进行json序列化
    logger.info(json_format(result))

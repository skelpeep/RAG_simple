import json

from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig
from atguigu.config.prompt import ITEM_NAME_EXTRACT_SYSTEM_PROMPT, ITEM_NAME_EXTRACT_TEMPLATE
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger
from atguigu.tool.mongo_client_tool import add_or_update_history, get_recent_history_list


class NodeItemNameConfirm(NodeBase):
    """
    节点功能：确认用户问题中的核心商品名称。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_item_name_confirm"

    def process(self, state: QueryGraphState):
        session_id = state.get("session_id")
        original_query = state.get('original_query')
        if not session_id:
            logger.error("会话ID不存在")
            raise ValueError("会话ID不存在")
        if not original_query:
            logger.error("原始查询不存在")
            raise ValueError("原始查询不存在")
        message_id = add_or_update_history(session_id, "user", original_query)
        history_list = get_recent_history_list(session_id)
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
                    {"role": "user", "content": ITEM_NAME_EXTRACT_TEMPLATE.format(history_text=history_content,
                                                                                  original_query=original_query)}]

        res = llm.invoke(messages)
        res_json = res.content
        if res_json.startswith("```json"):
            res_json = res_json.replace("```json", "").replace("```", "")
        res_dict = json.loads(res_json)






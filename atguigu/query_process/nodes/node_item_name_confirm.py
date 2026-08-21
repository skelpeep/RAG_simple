# atguigu/query_process/nodes/node_item_name_confirm.py

import json

from langchain.chat_models import init_chat_model
from atguigu.config.config import LLMConfig, MilvusConfig
from atguigu.config.prompt import ITEM_NAME_EXTRACT_SYSTEM_PROMPT, ITEM_NAME_EXTRACT_TEMPLATE, CHAT_CLARIFY_PROMPT
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, get_milvus_client, search_hybrid
from atguigu.tool.mongo_client_tool import add_or_update_history, get_recent_history_list, update_item_names_and_query


class NodeItemNameConfirm(NodeBase):
    """
    节点功能：确认用户问题中的核心书籍/主体名称。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_item_name_confirm"

    def handler_history(self, answer, final_item_names, message_id, rewritten_query, session_id):
        # message_id 传入时是「当前轮 user 消息」的 id
        user_message_id = message_id
        assistant_message_id = None
        if answer:
            assistant_message_id = add_or_update_history(session_id, role="assistant", text=answer)
        # 只回填「当前轮」的 user 消息和（若存在的）assistant 消息的主体信息，
        # 不要回填到历史所有消息，避免覆盖之前轮次已识别的主体
        ids = [i for i in (user_message_id, assistant_message_id) if i]
        if ids:
            update_item_names_and_query(ids, final_item_names, rewritten_query)
        return assistant_message_id or user_message_id

    def align_item_names(self, answer, final_item_names, final_search_item_names, item_names):
        confirm_item_names = [item.get("search_item_name") for item in final_search_item_names if
                              item.get("score") >= 0.85]
        option_item_name = [
            item.get("search_item_name")
            for item in final_search_item_names
            if 0.6 <= item.get("score") < 0.85]

        is_topic_search = False
        if confirm_item_names:
            final_item_names = confirm_item_names
            answer = ""
        elif option_item_name:
            final_item_names = []
            answer = f"请确认你想了解哪本书？{','.join(option_item_name)}"
        else:
            # 未匹配到具体书籍主体：很可能是“类别/场景/主题”类查询（如“科幻有声书”“通勤悬疑”）。
            # 保留提取到的主体词作为检索主题，走不带 item_name 过滤的向量检索，而不是直接判失败。
            final_item_names = [name for name in item_names if name]
            is_topic_search = True
            answer = ""
        return answer, final_item_names, is_topic_search

    def get_final_search_item_names(self, item_names):
        # 对item_names向量化，遍历进行混合搜索
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

            search_item_names = [
                {
                    "original_item_name": item_name,
                    "search_item_name": item.get("entity", {}).get("item_name", ""),
                    "score": item.get("distance")
                }
                for item in res[0]
            ]
            final_search_item_names.extend(search_item_names)
        return final_search_item_names

    def get_item_names(self, history_content, original_query):
        # 整理数据后就可以调大模型
        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_api_base,
            temperature=LLMConfig.llm_default_temperature
        )

        message = [{"role": "system", "content": ITEM_NAME_EXTRACT_SYSTEM_PROMPT},
                   {"role": "user", "content": ITEM_NAME_EXTRACT_TEMPLATE.format(history_text=history_content,
                                                                                 original_query=original_query)}]

        res = llm.invoke(message)
        # 对大模型的输出信息进行整理判断
        res_json = res.content
        # 大模型返回json有概率输出json的md代码块，需要去掉```json和```
        if res_json.startswith("```json"):
            res_json = res_json.replace("```json", "").replace("```", "")
        elif res_json.startswith("```"):
            res_json = res_json.replace("```", "")
        res_json = res_json.strip()
        # 把json转字典，取出item_name判断，有值就取出所有item_name的空白
        try:
            res_dict = json.loads(res_json)
        except Exception as e:
            logger.error(f"解析书籍主体JSON失败：{e}，原始输出：{res_json}")
            res_dict = {}
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
        return item_names, rewritten_query

    def get_history_content(self, state):
        session_id = state.get("session_id")
        if not session_id:
            logger.error("会话ID不存在")
            raise ValueError("会话ID不存在")

        original_query = state.get("original_query")
        if not original_query:
            logger.error("原始查询不存在")
            raise ValueError("原始查询不存在")

        message_id = add_or_update_history(session_id=session_id, role="user", text=original_query)
        history_list = get_recent_history_list(session_id)
        history_content = ""
        for history in history_list:
            role = history.get("role")
            text = history.get("text")
            content = f"{role}: {text}\n"
            history_content += content  # 拼接所有对话历史记录
        return history_content, message_id, original_query, session_id



    def get_chat_clarify_answer(self, history_content, original_query):
        """
        未识别出书籍/主体名称时，调用大模型生成一句友好的追问语，引导用户补充书籍信息。
        返回值为最终 answer，会被 handler_history 写入历史记录，实现多轮聊天。
        """
        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_api_base,
            temperature=LLMConfig.llm_default_temperature
        )
        messages = [{
            "role": "user",
            "content": CHAT_CLARIFY_PROMPT.format(
                history_text=history_content,
                original_query=original_query
            )
        }]
        res = llm.invoke(input=messages)
        answer = res.content.strip()
        return answer

    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """
        original_query = (state.get("original_query") or "").strip()
        query_image = (state.get("query_image") or "").strip()

        # 纯图片查询（只上传了图、未输入文字）：跳过主体提取与追问，
        # 用默认文本补全 rewritten_query，直接走检索分支（封面图搜图 + 无过滤文本检索），
        # 避免 original_query 为空导致链路报错。
        if query_image and not original_query:
            session_id = state.get("session_id")
            if not session_id:
                logger.error("会话ID不存在")
                raise ValueError("会话ID不存在")
            default_query = "识别这张图片对应的书籍内容"
            message_id = add_or_update_history(session_id=session_id, role="user", text="[图片]")
            return {
                "message_id": message_id,
                "original_query": default_query,
                "rewritten_query": default_query,
                "item_names": [],
                "is_topic_search": True,
                "answer": "",
                "history": get_recent_history_list(session_id, limit=10),
            }

        history_content, message_id, original_query, session_id = self.get_history_content(state)
        item_names, rewritten_query = self.get_item_names(history_content, original_query)

        # 拿到了item_name和rewritten_query,接下来对item_names向量化，从milvus的数据进行检索
        # 找相似度高的item_name
        #去milvus进行混合检索，先定义检索的工具
        answer = ""
        final_item_names =[]
        is_topic_search = False
        if item_names:
            final_search_item_names = self.get_final_search_item_names(item_names)

            answer, final_item_names, is_topic_search = self.align_item_names(answer, final_item_names, final_search_item_names, item_names)
        else:
            # LLM 未识别出任何书籍/主体名称：调用大模型生成一句自然的追问语，
            # 让路由走"回答"分支把追问语返回给用户，引导其补充书籍信息（实现聊天功能）。
            # 追问语随后由 handler_history 写入历史，下一轮即可结合上下文继续指代消解。
            answer = self.get_chat_clarify_answer(history_content, original_query)

        message_id = self.handler_history(answer, final_item_names, message_id, rewritten_query, session_id)

        return {
            "message_id":message_id,
            "original_query":original_query,
            "rewritten_query":rewritten_query,
            "item_names":final_item_names,
            "is_topic_search":is_topic_search,
            "answer":answer,
            "history":get_recent_history_list(session_id,limit=10)
        }




if __name__ == "__main__":

    # 模拟会话历史
    session_id = "test_001"
    add_or_update_history(session_id, "user", "咨询下烫金机。")
    add_or_update_history(session_id, "assistant", "您好。请问是哪个型号")
    add_or_update_history(session_id, "user", "hak180")
    add_or_update_history(session_id, "assistant", "具体有什么问题呢？")

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

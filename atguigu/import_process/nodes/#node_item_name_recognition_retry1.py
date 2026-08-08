import json

from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig
from atguigu.config.prompt import ITEM_NAME_SYSTEM_PROMPT, ITEM_NAME_USER_PROMPT_TEMPLATE
from atguigu.import_process.base import NodeBase
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client


class NodeItemNameRecognition(NodeBase):
    name = "node_item_name_recognition"
    def process(self, state):
        chunks = state.get("chunks")
        file_title = state.get("file_title")
        if not chunks:
            raise Exception
        if not file_title:
            raise  Exception

        chunk_k_list = chunks[:10]
        max_len = 10000
        content_str = "\n"
        for idx,chunk in enumerate(chunk_k_list,start=1):
            title = chunk.get("title")
            content = chunk.get("content")
            chunk_str = f"[切片{idx}]\n{file_title}\n{title}\n{content}\n\n"
            content_str += chunk_str
            if len(content_str) > max_len:
                break
        content_str = content_str[:max_len]

        if not content_str:
            logger.error("content为空")
            return {"file_title":file_title}

        llm = init_chat_model(
            model = LLMConfig.item_model,
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
        item_name = item_name.replace(" ", "").replace("\n", "").replace("\t", "")
        if not item_name:
            item_name = file_title

        milvus_client = get_milvus_client()
        if not milvus_client:
            logger.error("初始化milvus_client失败")
            raise Exception("初始化milvus_client失败")



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









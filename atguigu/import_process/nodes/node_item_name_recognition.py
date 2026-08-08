# atguigu/import_process/nodes/node_item_name_recognition.py
import json

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.logger import logger


class NodeItemNameRecognition(NodeBase):
    """
    主体识别节点：主体识别与标签提取
    """

    name = "node_item_name_recognition"

    def process(self, state: ImportGraphState):
        chunks = state.get("chunks")
        file_title = state.get("file_title")
        if not chunks:
            logger.error("chunks为空")
            raise Exception("chunks为空")

        if not file_title:
            logger.error("file_title为空")
            raise Exception("file_title为空")

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


        return state



if __name__ == '__main__':
    node = NodeItemNameRecognition()
    with open(r"D:\1neiwangtong\output\hak180产品安全手册\chunks.json","r",encoding="utf-8") as f:
        chunks = json.load(f)

    init_state = {
        "file_title": "hak180产品安全手册",
        "chunks": chunks,
    }
    res =node(init_state)
    logger.info(res)
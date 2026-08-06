# atguigu/import_process/nodes/node_document_split.py
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger


class NodeDocumentSplit(NodeBase):
    """
    文档切分节点：智能文档切片
    """

    name = "node_document_split"

    def get_md_content(self,state):
        md_path = state.get('md_path', "")
        if not md_path:
            logger.error("md_path路径未提供")
            raise ValueError("md_path路径未提供")
        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            logger.error("md_path路径不存在")
            raise FileNotFoundError("md_path路径不存在")

        file_title = state.get('file_title', "")
        if not file_title:
            file_title = md_path_obj.stem

        with open(md_path_obj, 'r', encoding='utf-8') as f:
            md_content = f.read()

        if not md_content:
            logger.error("md_content为空")
            raise ValueError("md_content为空")

        # 统一换行符
        md_content = md_content.replace("\r\n", "\n").replace("\r", "\n")

        return md_content,file_title,md_path_obj

    def get_section_list(self,md_content,file_title):
                # 按行切
        md_line_list =md_content.split("\n")
        # 按标题合并行，遍历找标题

        # 代码块正则
        code_pattern = r"^(`{3,}|~{3,})"
        # 定义是否再代码块内容的标识
        is_in_block =False #区分第几次碰到```| ~~~
        marker = None   # 标记遇到的是```还是~~~，下次遇到相同的时候就结束
        title_pattern = r'^\s*#{1,6}\s+.+'
        current_index =0
        section_list = []

        for idx,line in enumerate(md_line_list):
            line = line.strip()
            match = re.match(code_pattern,line)
            if match:
                if not is_in_block:
                    is_in_block=True
                    marker = match.group(1)
                    logger.info(f"开始匹配代码块：{marker}")
                else:
                    if marker == match.group(1):
                        is_in_block = False
                        marker = None
                        logger.info(f"结束匹配代码块")

            if not is_in_block and re.match(title_pattern,line):
                temp_list =md_line_list[current_index:idx]
                content = '\n'.join(temp_list)
                section_dict ={
                    "title": temp_list[0] if content.startswith("#") else "无标题",
                    "content": content,
                    "file_title": file_title
                }
                section_list.append(section_dict)

                current_index = idx

        section_list.append({
            "title": md_line_list[current_index],
            "content": '\n'.join(md_line_list[current_index:]),
            "file_title": file_title
        })


        logger.info(json_format(section_list))

        return section_list

    def get_final_section_list(self,section_list,file_title,md_path_obj):
        # 长切短合
        max_length = 300
        over_lap = 30
        final_section_list = []

        spliter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=max_length,
            chunk_overlap=over_lap
        )

        for section in section_list:
            content = section.get("content")
            title = section.get("title")

            real_content = content[len(title):] if content.startswith("#") else content

            if len(real_content) < max_length:
                final_section_list.append({
                    **section,
                    "part": 0
                })
                continue
            # 防止文件的表格被切断
            if "<table" in real_content:
                final_section_list.append({
                    **section,
                    "part": 0
                })
                continue

            # 切分
            split_chuck_list = spliter.split_text(real_content)
            for idx, split_chuck in enumerate(split_chuck_list, start=1):
                final_section_list.append({
                    "title": title,
                    "file_title": file_title,
                    "content": title + "\n\n" + split_chuck,
                    "part": idx
                })
        logger.info(json_format(final_section_list))

        # 备份chunks
        with open(md_path_obj.parent / "chunks.json", 'w', encoding='utf-8') as f:
            f.write(json_format(final_section_list))

        return final_section_list


    def process(self, state: ImportGraphState):

        md_content,file_title,md_path_obj=self.get_md_content( state)

        section_list =self.get_section_list(md_content,file_title)

        final_section_list = self.get_final_section_list(section_list,file_title,md_path_obj)

        return {
            "chucks": final_section_list
        }


if __name__ == '__main__':
    node = NodeDocumentSplit()
    init_state = {
        "md_path": r"D:\1neiwangtong\output\hak180产品安全手册\hak180产品安全手册_new.md",
        "file_title": "hak180产品安全手册"
    }
    result = node(init_state)
    logger.info(json_format(result))


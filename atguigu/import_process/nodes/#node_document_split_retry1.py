import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from atguigu.import_process.base import NodeBase
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger


class NodeDocumentSplit(NodeBase):
    name = "md_split"

    def get_md_file(self,state):
        file_path = state.get('md_path','')
        if not file_path:
            logger.error("文件路径未提供")
            raise Exception("文件路径未提供")
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.error('文件路径不存在')
            raise FileNotFoundError('文件路径不存在')
        file_title =state.get('file_title','')
        if not file_title:
            file_title = file_path_obj.stem

        with open(file_path_obj,mode="r",encoding="utf-8") as f:
            md_content=f.read()
        if not md_content:
            logger.error("文件为空")
            raise Exception('content文件为空')

        md_content = md_content.replace('\r\n','\n').replace('\r','\n')
        return file_path_obj,file_title,md_content

    def get_section_list(self,md_content,file_title):
        md_line_content = md_content.split('\n')
        title_pattern = r'^\s*#{1,6}\s+.+'
        code_pattern = r"^(`{3,}|~{3,})"
        is_in_block = False
        current_index = 0
        marker = None
        section_list = []

        for idx,line in enumerate(md_line_content):
            line = line.strip()
            match = re.match(code_pattern,line)
            if match:
                if not is_in_block:
                    is_in_block = True
                    marker = match.group(1)
                    logger.info(f"开始代码块{marker}")
                else:
                    if marker == match.group(1):
                        is_in_block = False
                        marker = None

            if not is_in_block and re.match(title_pattern,line):
                temp_list =md_line_content[current_index:idx]
                content = '\n'.join(temp_list)
                section_dict ={
                    "title":temp_list[0] if content.startswith("#") else "无标题",
                    "content":content,
                    "file_title":file_title
                }
                section_list.append(section_dict)
                current_index = idx

        section_list.append({
            "title":md_line_content[current_index],
            "content":'\n'.join(md_line_content[current_index:]),
            'file_title':file_title
        })
        return section_list

    def get_final_section_list(self,section_list,md_path_obj,file_title):
        max_length = 300
        over_lap = 30
        final_section_list =[]
        spliter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=max_length,
            chunk_overlap=over_lap,
        )

        for section in section_list:
            title = section.get('title')
            content = section.get('content')
            real_content = content[len(title):] if content.startswith("#") else content
            if len(real_content) < max_length:
                final_section_list.append({
                    **section,
                    "part":0
                })
                continue
            if "<table" in real_content:
                final_section_list.append({
                    **section,
                    "part": 0
                })
                continue

            spliter_chuck_list = spliter.split_text(real_content)
            for idx,split_chunk in enumerate(spliter_chuck_list,start=1):
                final_section_list.append({
                    "title":title,
                    "file_title":file_title,
                    "content":title + "\n\n" + split_chunk,
                    "part":idx
                })

        with open(md_path_obj.parent /"chunks.json","w",encoding="utf-8") as f:
            f.write(json_format(final_section_list))

        return final_section_list


    def process(self, state):
        file_path_obj,file_title,md_content = self.get_md_file(state)

        section_list =self.get_section_list(md_content,file_title)

        final_section_list = self.get_final_section_list(section_list,file_path_obj,file_title)

        return {
            "chunks":final_section_list
        }


if __name__ == '__main__':
    node = NodeDocumentSplit()
    init_state = {
        "md_path": r"D:\1neiwangtong\output\hak180产品安全手册\hak180产品安全手册_new.md",
        "file_title": "hak180产品安全手册"
    }
    result = node(init_state)
    logger.info(json_format(result))

# atguigu/import_process/nodes/node_md_img.py
import base64
import os
import re
import time
from collections import deque
from pathlib import Path

from langchain.chat_models import init_chat_model
from minio.deleteobjects import DeleteObject

from atguigu.config.config import LLMconfig, MinIoConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.minio_client_tool import get_minio_client


class NodeMDImg(NodeBase):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"


    def get_md_content(self,state):
        md_path = state.get("md_path", "")
        if not md_path:
            logger.error("md_path路径未提供")
            raise ValueError("md_path路径未提供")
        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            logger.error("md文件不存在")
            raise FileNotFoundError(f"md文件{md_path_obj}不存在")

        with open(md_path_obj, 'r', encoding="utf-8") as f:
            md_content = f.read()

        if not md_content:
            logger.error("md文件内容为空")
            raise ValueError("md文件内容为空")

        return md_content,md_path_obj

    def get_image_with_context_list(self,md_content,image_name_list,images_dir_path_obj):
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        MAX_CONTEXT_LENGTH = 250
        image_with_context_list = []
        for image_name in image_name_list:
            if Path(image_name).suffix.lower() not in IMAGE_EXTENSIONS:
                logger.warning(f"图片{image_name}格式不支持")
                continue

            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_name) + r"\)")
            match = pattern.search(md_content)

            if not match:
                logger.warning(f"图片{image_name}未引用")
                continue

            start, end = match.span()
            pre_text = md_content[max(0, start - MAX_CONTEXT_LENGTH):start]
            post_text = md_content[end:min(len(md_content), end + MAX_CONTEXT_LENGTH)]

            image_path = str(images_dir_path_obj / image_name)

            image_with_context_list.append(
                {
                    "image_name": image_name,
                    "pre_text": pre_text,
                    "post_text": post_text,
                    "image_path": image_path
                }
            )
        return image_with_context_list

    def get_image_with_summary_list(self,image_with_context_list):
        # 限频率 滑动门
        dq = deque(maxlen=30) # 双向队列

        llm = init_chat_model(
            model=LLMconfig.llm_default_model,
            model_provider="openai",
            base_url=LLMconfig.openai_api_base,
            api_key=LLMconfig.openai_api_key,
            temperature=LLMconfig.llm_default_temperature
        )

        image_with_summary_list = []
        for image_with_context in image_with_context_list:
            current_time = time.time()
            # 清理过期的请求
            while dq and current_time - dq[0] >60:
                dq.popleft()
            if dq and len(dq) == dq.maxlen:
                time2wait = 60 - (current_time - dq[0])
                if time2wait > 0:
                    logger.info(f"等待{time2wait}秒")
                    time.sleep(time2wait)
                    current_time = time.time()
                    while dq and current_time - dq[0] > 60:
                        dq.popleft()
            dq.append(current_time)

            with open(image_with_context.get("image_path",""), 'rb') as f:
                image_data = f.read()
                base64_str = base64.b64encode(image_data).decode('utf-8')

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64,"+ base64_str,
                            },
                        },
                        {"type": "text", "text":  f"""
                                        这是一张图片，图片上文部分为"{image_with_context.get("pre_text")}"，
                                        下文部分为"{image_with_context.get("post_text")}"，
                                        请用中文简要总结这张图片的摘要,字数在50字以内。"""},
                    ],
                },
            ] # 注意这里的逗号要删掉




            res =  llm.invoke(messages)
            image_with_summary_list.append(
                {
                    "image_name":image_with_context.get("image_name"),
                    "image_path":image_with_context.get("image_path"),
                    "summary":res.content
                }
            )
        return image_with_summary_list


    def get_image_with_summary_and_url_list(self,image_with_summary_list):
        # 4.上传图片到minio,构建url放入列表
        upload_dir = MinIoConfig.minio_img_dir
        minio_client = get_minio_client()

        old_image_list = minio_client.list_objects(bucket_name=MinIoConfig.minio_bucket_name, prefix=upload_dir, recursive=True)

        delete_image_list = [DeleteObject(obj.object_name) for obj in old_image_list]

        errors = minio_client.remove_objects(
            bucket_name=MinIoConfig.minio_bucket_name,
            delete_object_list=delete_image_list,
        )
        for error in errors:
            logger.error("error occurred when deleting object", error)


        image_with_summary_and_url_list = []
        for image_with_summary in image_with_summary_list:
            minio_client.fput_object(
                bucket_name=MinIoConfig.minio_bucket_name,
                object_name=upload_dir + "/" + image_with_summary.get("image_name"),
                file_path=image_with_summary.get("image_path")
            )
            url = f"http://{MinIoConfig.minio_endpoint}/{MinIoConfig.minio_bucket_name}/{upload_dir}/{image_with_summary.get('image_name')}"
            image_with_summary_and_url_list.append(
                {**image_with_summary,
                 "url": url
                 }
            )

        return image_with_summary_and_url_list

    def replace_md_image(self,image_with_summary_and_url_list,md_path_obj,md_content):
        for image_with_summary_and_url in image_with_summary_and_url_list:
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_with_summary_and_url.get("image_name")) + r"\)")
            # md_content=pattern.sub(f"![{image_with_summary_and_url.get('summary')}]({image_with_summary_and_url.get('url')})", md_content)
            # 用lambda可以规避特殊字符不报错
            md_content = pattern.sub(
                lambda m:f"![{image_with_summary_and_url.get('summary')}]({image_with_summary_and_url.get('url')})", md_content
            )

        new_md_path_obj =md_path_obj.parent / str(md_path_obj.stem + "_new.md")
        with open(new_md_path_obj, 'w', encoding='utf-8' ) as f:
            f.write(md_content)

        return new_md_path_obj,md_content

    def process(self, state: ImportGraphState):
        md_content,md_path_obj=self.get_md_content(state)

        # 构造图片存储路径
        images_dir_path_obj = md_path_obj.parent / "images"
        if not images_dir_path_obj.exists():
            return {
                "md_content": md_content,
            }

        image_name_list = os.listdir(images_dir_path_obj)
        if not image_name_list:
            logger.error("images文件夹为空")
            return {
                "md_content": md_content,
            }

        image_with_context_list=self.get_image_with_context_list(md_content, image_name_list, images_dir_path_obj)

        image_with_summary_list=self.get_image_with_summary_list(image_with_context_list)

        image_with_summary_and_url_list = self.get_image_with_summary_and_url_list(image_with_summary_list)

        new_md_path_obj,md_content = self.replace_md_image(image_with_summary_and_url_list, md_path_obj, md_content)

        return {
            "md_content": md_content
        }




if __name__ == '__main__':
    node = NodeMDImg()
    init_state={
        "md_path":r"D:\1neiwangtong\output\hak180产品安全手册\hak180产品安全手册.md"
    }
    result = node(init_state)
    logger.info(json_format(result))
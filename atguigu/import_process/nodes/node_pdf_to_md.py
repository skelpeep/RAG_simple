# atguigu/import_process/nodes/node_pdf_to_md.py

from pathlib import Path

from atguigu.config.config import MineruConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger


class NodePDFToMD(NodeBase):
    """
    PDF 转 Markdown 节点：PDF结构化解析
    """

    name = "node_pdf_to_md"

    def check_path(self,state):
        pdf_path = state.get("pdf_path", "")
        if not pdf_path:
            logger.error("pdf_path路径未提供")
            raise ValueError("pdf_path路径未提供")
        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            logger.error("pdf_path路径文件不存在")
            raise FileNotFoundError("pdf_path路径文件不存在")
        local_dir = state.get('local_dir','')
        if not local_dir:
            logger.error("local_dir未提供")
            raise ValueError("local_dir未提供")

        local_dir_obj = Path(local_dir)
        if not local_dir_obj.exists():
            local_dir_obj.mkdir(parents=True, exist_ok=True)
        return pdf_path,local_dir_obj,pdf_path_obj

    def upload_pdf(self,pdf_path,pdf_path_obj):
        import requests


        token = MineruConfig.mineru_token
        url = f"{MineruConfig.mineru_base_url}/file-urls/batch"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "files": [
                {"name": f"{pdf_path_obj.name}", "data_id": "abcd"}
            ],
            "model_version": "vlm"
        }
        file_path = [f"{pdf_path}"]

        response = requests.post(url, headers=header, json=data)
        if response.status_code != 200:
            logger.error('上传pdf请求失败')
            raise Exception('上传pdf请求失败')

        logger.info('上传PDF文件成功')
        result = response.json()
        if result["code"] != 0:
            logger.error('上传pdf请求数据失败')
            raise Exception('上传pdf请求数据失败')
        logger.info('上传PDF文件请求成功')

        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]

        for i in range(0, len(urls)):
            with open(file_path[i], 'rb') as f:
                res_upload = requests.put(urls[i], data=f)
                if res_upload.status_code == 200:
                    logger.info(f"{urls[i]} 上传成功")
                else:
                    logger.error(f"{urls[i]} 上传失败")
        return batch_id

    def get_md_zip_url(self,batch_id):
        import time
        import requests
        token = MineruConfig.mineru_token
        batch_id = batch_id
        url = f"{MineruConfig.mineru_base_url}/extract-results/batch/{batch_id}"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        total_time = 300
        use_time = 0
        while True:
            start_time = time.time()
            try:
                res = requests.get(url, headers=header)
                if res.status_code != 200:
                    logger.error('获取PDF处理结果失败')
                    raise Exception('获取PDF处理结果失败')

                result = res.json()
                if result["code"] != 0:
                    logger.error('获取PDF处理结果请求数据失败')
                    raise Exception('获取PDF处理结果请求数据失败')
                data = result["data"]['extract_result'][0]
                if data['state'] != 'done':
                    logger.info('PDF正在处理中，请稍等')
                    raise Exception('PDF正在处理中，请稍等')
                zip_url = data['full_zip_url']
                return zip_url
            except Exception as e:
                logger.error(f'pdf处理异常,{e}')
                end_time = time.time()
                use_time += end_time - start_time
                if use_time > total_time:
                    logger.error('pdf处理超时')
                    raise Exception('pdf处理超时,请稍后再试')
                continue

    def download_zip_handler(self,md_zip_url,local_dir_obj,pdf_path_obj):
        import requests
        md_zip_res = requests.get(md_zip_url)
        if md_zip_res.status_code != 200:
            logger.error('下载PDF文件处理结果zip压缩包请求失败')
            raise Exception('下载PDF文件处理结果zip压缩包请求失败')
        md_zip_content = md_zip_res.content

        md_zip_path_obj = local_dir_obj / f"{pdf_path_obj.stem}.zip"

        with open(md_zip_path_obj, 'wb') as f:
            f.write(md_zip_content)

        import zipfile
        import shutil
        unzip_file_content = zipfile.ZipFile(md_zip_path_obj)
        unzip_file_path_obj = local_dir_obj / f"{pdf_path_obj.stem}"

        if unzip_file_path_obj.exists():
            shutil.rmtree(unzip_file_path_obj)
        unzip_file_path_obj.mkdir(parents=True, exist_ok=True)

        unzip_file_content.extractall(unzip_file_path_obj)

        origin_md_path_obj = unzip_file_path_obj / "full.md"
        new_md_path_obj = origin_md_path_obj.with_name(f"{pdf_path_obj.stem}.md")
        origin_md_path_obj.rename(new_md_path_obj)

        with open(new_md_path_obj, 'r', encoding='utf-8') as f:
            md_content = f.read()
        return new_md_path_obj,md_content





    def process(self, state: ImportGraphState):
        pdf_path, local_dir_obj, pdf_path_obj=self.check_path(state)

        batch_id =self.upload_pdf(pdf_path,pdf_path_obj)

        zip_url=self.get_md_zip_url(batch_id)

        new_md_path_obj,md_content=self.download_zip_handler(zip_url,local_dir_obj,pdf_path_obj)

        return {
            "md_path": str(new_md_path_obj), "md_content": md_content
        }



if __name__ == '__main__':
    node = NodePDFToMD()
    init_state = {
        "pdf_path": r"D:\1neiwangtong\渊哥\视频资料相关\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册.pdf",
        "local_dir": r"D:\1neiwangtong\output"
    }
    result = node(init_state)
    logger.info(json_format(result))




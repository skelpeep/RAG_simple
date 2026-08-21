# atguigu/tool/multimodal_embedding_tool.py
"""
多模态向量化工具：把「文本」与「图片」映射到同一个向量空间，支撑封面图与内容的联合检索。

设计说明：
- 图文对齐的多模态向量（CLIP 类 / 阿里百炼 tongyi-embedding-vision-plus 等）中，
  文本向量与图片向量可直接比较相似度，因此：
    * 封面图片 -> image_vector（图片向量）
    * 封面描述文本 -> text_vector（文本向量，与 image_vector 同空间）
  检索时既可用「图片」搜图，也可用「文本」搜图（跨模态）。
- 供应商通过环境变量 MM_EMBEDDING_PROVIDER 切换，模型与 API 由用户自行配置。
  新增供应商只需继承 MultimodalEmbeddingClient 实现 embed_text / embed_images 两个方法。

支持供应商：
  1. dashscope —— 阿里云百炼多模态向量（qwen3-vl-embedding / tongyi-embedding-vision-plus）
  2. openai    —— 任意 OpenAI 兼容多模态向量接口（SiliconFlow Qwen3-VL-Embedding / Jina CLIP 等）
"""
import base64
from http import HTTPStatus
from pathlib import Path
from typing import List

from atguigu.config.config import MultimodalConfig
from atguigu.tool.logger import logger


def image_to_base64_data_url(image: str) -> str:
    """把「本地路径 / 公网URL / 裸base64 / data URL」统一为 base64 data URL。

    - data:image/... 开头：原样返回
    - http(s) 开头：当作公网 URL 原样返回（交由 API 端下载）
    - 本地文件存在：读取并编码为 data URL
    - 其它：视为裸 base64，补上 data URL 前缀
    """
    image = (image or "").strip()
    if not image:
        raise ValueError("图片输入为空")
    if image.startswith("data:image/"):
        return image
    if image.startswith(("http://", "https://")):
        return image
    p = Path(image)
    if p.exists():
        suffix = p.suffix.lower().lstrip(".") or "jpeg"
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{suffix};base64,{b64}"
    return f"data:image/jpeg;base64,{image}"


class MultimodalEmbeddingClient:
    """多模态向量客户端抽象基类。"""

    def embed_text(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_images(self, images: List[str]) -> List[List[float]]:
        raise NotImplementedError


class DashscopeMultimodalEmbeddingClient(MultimodalEmbeddingClient):
    """阿里云百炼多模态向量（独立向量模式：图文分别生成、同一空间对齐）。"""

    def __init__(self):
        import dashscope
        dashscope.api_key = MultimodalConfig.mm_embedding_api_key
        # workspace 专属 key（sk-ws-...）需配合 workspace 的 DashScope 原生地址
        # （如 https://xxx.cn-beijing.maas.aliyuncs.com/api/v1，注意不是 compatible-mode/v1）
        base = (MultimodalConfig.mm_embedding_base_url or "").strip()
        if base:
            dashscope.base_http_api_url = base
        self.dashscope = dashscope
        self.model = MultimodalConfig.mm_embedding_model
        self.dimension = MultimodalConfig.mm_embedding_dim

    def _call(self, contents: List[dict]) -> List[List[float]]:
        kwargs = {"model": self.model, "input": contents}
        if self.dimension and self.dimension > 0:
            kwargs["dimension"] = self.dimension
        resp = self.dashscope.MultiModalEmbedding.call(**kwargs)
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(f"多模态向量化失败: {resp.code} {resp.message}")
        embeddings = (resp.output or {}).get("embeddings", [])
        return [list(item["embedding"]) for item in embeddings]

    def embed_text(self, texts: List[str]) -> List[List[float]]:
        return self._call([{"text": t} for t in texts])

    def embed_images(self, images: List[str]) -> List[List[float]]:
        return self._call([{"image": image_to_base64_data_url(i)} for i in images])


class OpenAICompatibleMultimodalEmbeddingClient(MultimodalEmbeddingClient):
    """OpenAI 兼容的多模态向量接口。

    支持两种 input 编排格式（通过 MM_EMBEDDING_INPUT_FORMAT 切换）：
      - openai（默认）：{"type":"text","text":...} / {"type":"image_url","image_url":{"url":...}}
      - jina           ：{"text":...} / {"image":...}
    """

    def __init__(self):
        import requests
        self.requests = requests
        self.base_url = (MultimodalConfig.mm_embedding_base_url or "").rstrip("/")
        self.api_key = MultimodalConfig.mm_embedding_api_key
        self.model = MultimodalConfig.mm_embedding_model
        self.input_format = (MultimodalConfig.mm_embedding_input_format or "openai").lower()
        if not self.base_url:
            logger.warning("MM_EMBEDDING_BASE_URL 未配置，OpenAI 兼容多模态向量可能无法调用")

    def _post(self, payload: dict) -> List[List[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = self.requests.post(
            f"{self.base_url}/embeddings", json=payload, headers=headers, timeout=60
        )
        if resp.status_code != 200:
            raise RuntimeError(f"多模态向量化失败({resp.status_code}): {resp.text[:500]}")
        data = resp.json().get("data", [])
        data = sorted(data, key=lambda x: x.get("index", 0))
        return [list(item["embedding"]) for item in data]

    def _build_input(self, texts=None, images=None) -> List[dict]:
        items = []
        if self.input_format == "jina":
            for t in (texts or []):
                items.append({"text": t})
            for i in (images or []):
                items.append({"image": image_to_base64_data_url(i)})
        else:
            for t in (texts or []):
                items.append({"type": "text", "text": t})
            for i in (images or []):
                items.append(
                    {"type": "image_url", "image_url": {"url": image_to_base64_data_url(i)}}
                )
        return items

    def embed_text(self, texts: List[str]) -> List[List[float]]:
        return self._post({"model": self.model, "input": self._build_input(texts=texts)})

    def embed_images(self, images: List[str]) -> List[List[float]]:
        return self._post({"model": self.model, "input": self._build_input(images=images)})


_multimodal_client = None


def get_multimodal_embedding_client() -> MultimodalEmbeddingClient:
    """获取多模态向量客户端（懒加载单例）。"""
    global _multimodal_client
    if _multimodal_client is None:
        provider = (MultimodalConfig.mm_embedding_provider or "dashscope").lower()
        if provider == "dashscope":
            _multimodal_client = DashscopeMultimodalEmbeddingClient()
        elif provider in ("openai", "openai-compatible", "jina", "siliconflow"):
            _multimodal_client = OpenAICompatibleMultimodalEmbeddingClient()
        else:
            raise ValueError(f"不支持的多模态向量供应商: {provider}")
    return _multimodal_client


def embed_multimodal_text(texts: List[str]) -> List[List[float]]:
    return get_multimodal_embedding_client().embed_text(texts)


def embed_multimodal_images(images: List[str]) -> List[List[float]]:
    return get_multimodal_embedding_client().embed_images(images)


if __name__ == "__main__":
    # 本地自测：需先在 .env 配置好 MM_EMBEDDING_* 相关变量
    texts = ["刘慈欣《三体》科幻有声书"]
    print("text vec dim:", len(embed_multimodal_text(texts)[0]))

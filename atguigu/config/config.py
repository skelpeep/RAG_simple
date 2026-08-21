import os

from dotenv import load_dotenv

load_dotenv(override=True)


class MineruConfig:
    mineru_token=os.getenv("MINERU_TOKEN")
    mineru_base_url=os.getenv("MINERU_BASE_URL")

class LLMConfig:
    openai_api_key=os.getenv("OPENAI_API_KEY")
    openai_api_base=os.getenv("OPENAI_API_BASE")
    llm_default_model=os.getenv("LLM_DEFAULT_MODEL")
    llm_default_temperature=float(os.getenv("LLM_DEFAULT_TEMPERATURE"))
    vl_model=os.getenv("VL_MODEL")
    item_model=os.getenv("ITEM_MODEL")


class MinIoConfig:
    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_access_key = os.getenv("MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY")
    minio_bucket_name = os.getenv("MINIO_BUCKET_NAME")
    minio_img_dir = os.getenv("MINIO_IMG_DIR")


class EmbeddingConfig:
    bge_m3_path=os.getenv("BGE_M3_PATH")
    bge_m3=os.getenv("BGE_M3")
    bge_device=os.getenv("BGE_DEVICE")
    # 特殊处理：将.env中的1/0转为布尔值，兼容常见的数字/字符串格式
    bge_fp16=True if os.getenv("BGE_FP16") in ("1", "True", "true") else False


class MilvusConfig:
    # ====================
    # Vector Database (Milvus)
    # ====================
    # Milvus 连接地址
    milvus_url = os.getenv("MILVUS_URL")
    # 知识库切片集合名
    chunks_collection = os.getenv("CHUNKS_COLLECTION")
    # 书籍主体集合名（存储书名/作者/内容类型/类别等主体元数据）
    item_name_collection = os.getenv("ITEM_NAME_COLLECTION")

class MongoConfig:
    mongo_url = os.getenv("MONGO_URL")
    mongo_db_name = os.getenv("MONGO_DB_NAME")


class McpConfig:
    mcp_base_url=os.getenv("MCP_DASHSCOPE_BASE_URL")
    api_key=os.getenv("OPENAI_API_KEY")


class RerankConfig:
    rerank_base_url = os.getenv("RERANK_BASE_URL")
    rerank_api_key = os.getenv("RERANK_API_KEY")


class ImportConfig:
    # 导入文件的本地暂存目录（可通过环境变量 IMPORT_OUTPUT_DIR 覆盖，默认项目内 data/import）
    output_dir = os.getenv("IMPORT_OUTPUT_DIR", "data/import")



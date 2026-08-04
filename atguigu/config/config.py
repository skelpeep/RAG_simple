import os
from dotenv import load_dotenv
load_dotenv(override=True)


class MineruConfig:
    mineru_token=os.getenv("MINERU_TOKEN")
    mineru_base_url=os.getenv("MINERU_BASE_URL")

class LLMconfig:
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
# atguigu/import_process/state.py

from typing import TypedDict

class ImportGraphState(TypedDict):
    """
    图的状态定义，包含所有节点产生和消费的数据字段
    """
    task_id: str # 任务唯一ID，用于追踪日志

    #流程控制标记
    is_md_read_enabled: bool    # 是否启用 Markdown 读取路径
    is_pdf_read_enabled: bool   # 是否启用 PDF 读取路径

    # 路径相关
    local_dir: str  # 当前工作目录或输出目录
    local_file_path: str    # 原始输入文件路径
    file_title: str # 文件标题（文件名去后缀）
    pdf_path: str   # PDF 文件路径 (如果输入是PDF)
    md_path: str    # Markdown 文件路径 (转换后或直接输入的)
    source_path: str  # 来源路径或资源链接（如 MinIO 对象名 / 本地路径），用于检索溯源

    # 内容数据
    md_content: str # Markdown 的全文内容
    chunks: list    # 切片列表
    item_name: str  # 识别主体/条目名称（例如：刘慈欣《三体》）
    book_metadata: dict  # 书籍结构化元数据：book_name书名 / author作者 / content_type内容类型 / category类别 / duration时长
    user_metadata: dict  # 用户上传时人工指定的元数据（可选），非空字段会覆盖自动识别结果
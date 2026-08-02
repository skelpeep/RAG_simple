import json

def json_format(data):
    """
    格式化json字符串
    :param json_str:
    :return:
    """
    result = json.dumps(data, indent=4, ensure_ascii=False)
    return result
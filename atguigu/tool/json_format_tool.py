import json


import numpy as np

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)      # 这里会把 float16 转为 Python float
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)




def json_format(data):
    """
    格式化json字符串
    :param json_str:
    :return:
    """
    result = json.dumps(data, indent=4, ensure_ascii=False,cls=NumpyEncoder)
    return result
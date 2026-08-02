

from abc import abstractmethod,ABC

from atguigu.tool.logger import logger


class NodeBase(ABC):
    name = "node_base"
    def __init__(self):
        if self.name == "node_base":
            raise Exception(f"{self.__class__.__name__}必须重写父类的name属性")



    @abstractmethod
    def process(self, state):
        pass

    def __call__(self, state):
        try:
            logger.info(f"{self.name}开始")
            result =self.process(state)
            logger.info(f"{self.name}结束")
            return result
        except Exception as e:
            logger.error(f"{self.name}发生错误：{e}")
            raise e















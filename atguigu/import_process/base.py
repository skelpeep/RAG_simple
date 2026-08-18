import time
from abc import abstractmethod,ABC

from atguigu.tool.logger import logger
from atguigu.tool.task_utils import add_running_task, add_done_task, add_node_duration


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
            task_id =state.get("task_id")
            add_running_task(task_id, self.name)
            start_time =time.time()

            result =self.process(state)
            logger.info(f"{self.name}结束")
            add_done_task(task_id, self.name)
            end_time = time.time()

            add_node_duration(task_id,self.name,end_time-start_time)
            return result
        except Exception as e:
            logger.error(f"{self.name}发生错误：{e}")
            raise e















from atguigu.import_process.base import NodeBase
from atguigu.tool.logger import logger


class TestBase(NodeBase):
    name ="test1"
    def process(self, state):
        logger.info("测试")
        return state


if __name__ == '__main__':
    tes = TestBase()
    init ={}
    result = tes(init)
    logger.info(result)

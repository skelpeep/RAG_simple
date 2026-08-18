"""
1.发送上传请求:先创建task_id(uuid),给出local_dir(输出地址，自己拼接，用路径+时间的方式）
2.检查路径是否存在，不存在创建
3.打开路径保存上传的文件
4.上传到minio
5.后台添加任务(run_main_graph)，将主进程添加到后台
6.为之前的任务add_running_task,add_done_task,为run_main_graph添加3个update_task_status
"""
























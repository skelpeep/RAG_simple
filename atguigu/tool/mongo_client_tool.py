import time

from pymongo import MongoClient

from atguigu.config.config import MongoConfig

mongo_client = None

def get_mongo_client():
    global mongo_client
    if not mongo_client:
        mongo_client = MongoClient(MongoConfig.mongo_url)
    return  mongo_client

collection = None
db = None
def get_mongo_collection():
    global collection
    global db
    mongo_client=get_mongo_client()
    if not db:
        db = mongo_client[MongoConfig.mongo_db_name]
    if not collection:
        collection = db["chat_history"]
        collection.create_index([("_id",1),("ts",-1),("session_id",1)])
    return collection

def get_recent_history_list(session_id,limit=10):
    collection = get_mongo_collection()
    result= collection.find({"session_id":session_id}).sort("ts",-1).limit(limit)
    print(result)
    return list(result) # 拿到的是游标对象，需要自己强转


def add_or_update_history(session_id,role,text,rewritten_query=None,item_name=None,ts=None,_id=None):
    # 封装增和改数据库写成一个方法或者函数，因为传递参数只有id不同
    collection = get_mongo_collection()
    if _id:  # 修改
        data ={
            "role":role,
            "text":text,
            "rewritten_query":rewritten_query,
            "item_name":item_name,
            "ts":ts or time.time(),
            "_id":_id,
            "session_id":session_id
        }
        collection.update_one({"_id":_id}, {"$set":data})
        return _id
    else:  # 新增
        data = {
            "role": role,
            "text": text,
            "rewritten_query": rewritten_query,
            "item_name": item_name,
            "ts": ts or time.time(),
            "session_id": session_id
        }
        result =collection.insert_one(data)
        print(result.inserted_id)
        return result.inserted_id

def clear_history(session_id):
    collection =get_mongo_collection()
    collection.delete_many({"session_id":session_id})

def update_item_names_and_query(session_id, item_name=None, rewritten_query=None):
    collection=get_mongo_collection()
    data = {
        "session_id": session_id,
        "item_name": item_name,
        "rewritten_query": rewritten_query
    }
    collection.updateOne({"session_id":session_id}, {"$set":data})

if __name__ == '__main__':
    # add_or_update_history("test_001", "user", "咨询下烫金机。")
    # add_or_update_history("test_001", "assistant", "您好。请问是哪个型号")
    # result = add_or_update_history("test_001", "user", "hak180")
    # print(result,type(result))
    # add_or_update_history("test_001", "assistant", "具体有什么问题呢？")


    # result = get_recent_history_list("test_001")
    # print(result)


    clear_history("test_001")
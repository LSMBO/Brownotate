from pymongo import MongoClient
from utils import load_config

config = load_config()
client = MongoClient(config['MONGO_URI'])
db = client['brownotate-db']
users_collection = db['users']
runs_collection = db['runs']
dbsearch_collection = db['dbsearch']
processes_collection = db['processes']

if 'users' not in db.list_collection_names():
    db.create_collection('users')
if 'runs' not in db.list_collection_names():
    db.create_collection('runs')
if 'dbsearch' not in db.list_collection_names():
    db.create_collection('dbsearch')

def find(collection_name, query):    
    try:
        collection = db[collection_name]
        results = list(collection.find(query))
        for doc in results:
            doc['_id'] = str(doc['_id'])
        return {'status': 'success', 'data': results}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
    
def find_one(collection_name, query):
    try:
        collection = db[collection_name]
        result = collection.find_one(query)
        if result:
            result['_id'] = str(result['_id'])
        return {'status': 'success', 'data': result}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def insert_one(collection_name, query):
    try:
        collection = db[collection_name]
        result = collection.insert_one(query)
        return {'status': 'success', 'inserted_id': result.inserted_id}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
    
def update_one(collection_name, query, update):
    try:
        collection = db[collection_name]
        result = collection.update_one(query, update)
        if result.matched_count > 0:
            return {'status': 'success'}
        else:
            return {'status': 'error', 'message': 'No documents matched the query'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def delete_one(collection_name, query):
    try:
        collection = db[collection_name]
        result = collection.delete_one(query)
        if result.deleted_count > 0:
            return {'status': 'success', 'deleted_count': result.deleted_count}
        else:
            return {'status': 'error', 'message': 'No documents matched the query'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


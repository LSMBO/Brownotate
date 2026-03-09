from pymongo import MongoClient
from .utils import load_config

config = load_config()
client = MongoClient(config['MONGO_URI'])
db = client['brownotate-db']
users_collection = db['users']
runs_collection = db['runs']
taxonomy_collection = db['taxonomy']
ensembl_collection = db['ensembl']
refseq_collection = db['refseq']
genbank_collection = db['genbank']
dnaseq_collection = db['dnaseq']
uniprot_collection = db['uniprot']
processes_collection = db['processes']

if 'users' not in db.list_collection_names():
    db.create_collection('users')
if 'runs' not in db.list_collection_names():
    db.create_collection('runs')
if 'taxonomy' not in db.list_collection_names():
    db.create_collection('taxonomy')
if 'ensembl' not in db.list_collection_names():
    db.create_collection('ensembl')
if 'refseq' not in db.list_collection_names():
    db.create_collection('refseq')
if 'genbank' not in db.list_collection_names():
    db.create_collection('genbank')
if 'dnaseq' not in db.list_collection_names():
    db.create_collection('dnaseq')
if 'uniprot' not in db.list_collection_names():
    db.create_collection('uniprot')

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
        find_result = collection.find_one(query)
        if not find_result:
            return {'status': 'error', 'message': 'No documents matched the query'}
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

def delete(collection_name, query):
    try:
        collection = db[collection_name]
        result = list(collection.delete_many(query))
        if result.deleted_count > 0:
            return {'status': 'success', 'deleted_count': result.deleted_count}
        else:
            return {'status': 'error', 'message': 'No documents matched the query'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


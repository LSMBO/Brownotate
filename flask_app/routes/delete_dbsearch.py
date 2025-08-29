from flask import Blueprint, request, jsonify
from flask_app.database import delete_one

delete_dbsearch_bp = Blueprint('delete_dbsearch_bp', __name__)

@delete_dbsearch_bp.route('/delete_dbsearch', methods=['POST'])
def delete_dbsearch():
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    
    dbsearch_run_id = dbsearch['run_id']
    print(f"User: {user}, Deleting dbsearch with run_id: {dbsearch_run_id}")
    query = {'run_id': dbsearch_run_id}
    return delete_one('dbsearch', query)
        
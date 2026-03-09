from flask import Blueprint, request, jsonify
from flask_app.database import db
import datetime

cancel_dbsearch_bp = Blueprint('cancel_dbsearch_bp', __name__)

@cancel_dbsearch_bp.route('/cancel_dbsearch', methods=['POST'])
def cancel_dbsearch():
    """
    Delete all database search results for a given user and taxonomy
    that were created in the last 10 minutes (to handle cancelled searches)
    """
    try:
        user = request.json.get('user')
        taxid = request.json.get('taxid')
        
        if not user or not taxid:
            return jsonify({'status': 'error', 'message': 'Missing user or taxid'}), 400
        
        # Calculate the time threshold (10 minutes ago)
        now = datetime.datetime.now()
        time_threshold = now - datetime.timedelta(minutes=10)
        threshold_str = time_threshold.strftime("%d%m%Y-%H%M%S")
        
        # Collections to clean
        collections = ['uniprot', 'ensembl', 'refseq', 'genbank', 'dnaseq']
        deleted_counts = {}
        
        for collection_name in collections:
            try:
                collection = db[collection_name]
                # Delete documents matching user and taxid created after the threshold
                result = collection.delete_many({
                    'user': user,
                    'taxid': taxid,
                    'date': {'$gte': threshold_str}
                })
                deleted_counts[collection_name] = result.deleted_count
            except Exception as e:
                print(f"Error deleting from {collection_name}: {str(e)}")
                deleted_counts[collection_name] = 0
        
        return jsonify({
            'status': 'success',
            'message': 'Cancelled search results deleted',
            'deleted_counts': deleted_counts
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }), 500

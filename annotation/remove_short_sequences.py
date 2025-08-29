from Bio import SeqIO
import os
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify

run_remove_short_sequences_bp = Blueprint('run_remove_short_sequences_bp', __name__)

@run_remove_short_sequences_bp.route('/run_remove_short_sequences', methods=['POST'])
def run_remove_short_sequences():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    annotation_file = request.json.get('annotation_file')
    min_length = int(parameters['annotationSection']['minLength'])
    
    valid_records = []
    sequence_removed = 0
    print(f"from {os.getcwd()} open file {annotation_file}")
    with open(annotation_file, "r") as initial_annotation:
        for record in SeqIO.parse(initial_annotation, "fasta"):
            sequence = str(record.seq)
            if len(sequence) >= min_length: 
                valid_records.append(record)
            else:
                sequence_removed += 1

    with open(annotation_file, "w") as updated_annotation:
        SeqIO.write(valid_records, updated_annotation, "fasta")

    return jsonify({'status': 'success', 'data': {'annotation_file': annotation_file, 'sequence_removed': sequence_removed}, 'timer': timer.stop(start_time)}), 200

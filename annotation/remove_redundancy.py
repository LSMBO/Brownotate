from Bio import SeqIO
import os
from timer import timer
from utils import load_config
from flask import Blueprint, request, jsonify

run_remove_redundancy_bp = Blueprint('run_remove_redundancy_bp', __name__)

@run_remove_redundancy_bp.route('/run_remove_redundancy', methods=['POST'])
def run_remove_redundancy():
    start_time = timer.start()
    parameters = request.json.get('parameters')
    annotation_file = request.json.get('annotation_file')
    
    if parameters['annotationSection']['removeStrict']:
        result = remove_duplicate_sequences(annotation_file)
    else: # parameters['annotationSection']['removeSoft']
        result = remove_redundancy_and_subsequences(annotation_file)

    return jsonify({'status': 'success', 'data': result, 'timer': timer.stop(start_time)}), 200

def remove_duplicate_sequences(annotation_file):
    sequences = []
    sequence_removed = 0
    filtered_records = []

    with open(annotation_file, "r") as f:
        for record in SeqIO.parse(f, "fasta"):
            sequence = str(record.seq)
            if not any(sequence == existing_seq for existing_seq in sequences):
                sequences.append(sequence)
                filtered_records.append(record)
            else:
                sequence_removed += 1

    with open(annotation_file, "w") as f:
        SeqIO.write(filtered_records, f, "fasta")

    return {
        'annotation_file': annotation_file,
        'sequence_removed': sequence_removed
    }

    
def remove_redundancy_and_subsequences(annotation_file):
    sequences = []
    sequence_removed = 0
    filtered_records = []

    with open(annotation_file, "r") as f:
        for record in SeqIO.parse(f, "fasta"):
            sequence = str(record.seq)
            if not any(sequence in existing_seq or existing_seq in sequence for existing_seq in sequences):
                sequences.append(sequence)
                filtered_records.append(record)
            else:
                sequence_removed += 1

    with open(annotation_file, "w") as f:
        SeqIO.write(filtered_records, f, "fasta")

    return {
        'annotation_file': annotation_file,
        'sequence_removed': sequence_removed
    }

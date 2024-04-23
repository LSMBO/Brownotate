from Bio import SeqIO
import os

def fasta_split(file_path, cpus):
    # Open the FASTA file
    fasta_records = SeqIO.parse(file_path, 'fasta')
    fasta_records = sorted(fasta_records, key=lambda x: len(x.seq), reverse=True)

    # Get the total number of sequences
    total_sequences = sum(1 for seq in fasta_records)
    
    # Check if the total number of sequences is less than cpus
    if total_sequences < cpus:
        cpus = total_sequences
        
    # Create the directory if it does not exist
    if not os.path.exists('annotation'):
        os.makedirs('annotation')
    
    # Create n empty lists
    lists = [[] for i in range(cpus)]
    
    # Assign each record to one of the n lists
    list_idx = 0
    for record in fasta_records:
        lists[list_idx].append(record)
        list_idx = (list_idx + 1) % cpus
    
    # Write each list of records to a separate file
    file_names = []
    for i, record_list in enumerate(lists):
        file_name = os.path.join('annotation', 'file_{}.fasta'.format(i+1))
        SeqIO.write(record_list, file_name, 'fasta')
        file_names.append(file_name)
    
    return file_names

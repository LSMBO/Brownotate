from Bio import SeqIO

def remove_short_sequences(annotation, min_length):
    valid_records = []
    
    with open(annotation, "r") as initial_annotation:
        for record in SeqIO.parse(initial_annotation, "fasta"):
            sequence = str(record.seq)
            if len(sequence) >= min_length: 
                valid_records.append(record)

    with open(annotation, "w") as updated_annotation:
        SeqIO.write(valid_records, updated_annotation, "fasta")

    return annotation

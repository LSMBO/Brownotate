from Bio import SeqIO

def remove_redundancy(annotation, mode):
    if mode == 1:
        result = remove_duplicate_sequences(annotation)
    if mode == 2:
        result = remove_redundancy_and_subsequences(annotation)
    return result

def remove_duplicate_sequences(annotation):
    sequences = {}
    with open(annotation, "r") as handle:
        for record in SeqIO.parse(handle, "fasta"):
            sequence = str(record.seq)
            if sequence not in sequences:
                sequences[sequence] = record
    with open(annotation, "w") as handle:
        SeqIO.write(sequences.values(), handle, "fasta")
    return annotation

def remove_redundancy_and_subsequences(annotation):
    sequences = {}
    with open(annotation, "r") as handle:
        for record in SeqIO.parse(handle, "fasta"):
            sequence = str(record.seq)
            found = False
            for existing_seq in sequences:
                if sequence in existing_seq:
                    found = True
                    break
                elif existing_seq in sequence:
                    del sequences[existing_seq]
                    break
            if not found:
                sequences[sequence] = record
    with open(annotation, "w") as handle:
        SeqIO.write(sequences.values(), handle, "fasta")
    return annotation

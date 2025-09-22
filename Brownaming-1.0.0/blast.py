import os, subprocess, multiprocessing
from Bio import SeqIO
from blast_reader import blast_reader

def parallel_blast(protein_file, database_file, output_file, cpus, short=False):
    db_name = make_blast_db(database_file)
    try:
        base_name = os.path.basename(database_file).rsplit(".", 1)[0]
        parts = base_name.split("_")
        ancestor_name = "_".join(parts[1:-1]) if len(parts) > 2 else parts[1]
        ancestor_rank = parts[-1]
    except (ValueError, IndexError):
        ancestor_name, ancestor_rank = None, None

    protein_files = fasta_split(protein_file, "split", cpus)
    
    if os.path.exists("blast"):
        for filename in os.listdir("blast"):
            os.remove(f"blast/{filename}")
    else:
        os.makedirs("blast")
                
    results = []
    with multiprocessing.Pool() as pool:
        for i, file in enumerate(protein_files):
            result = pool.apply_async(run_blast, args=(file, db_name, i+1))
            results.append(result)
 
        results_files = []
        for result in results:
            results_files.append(result.get())
        concatenate_files(results_files, "blast/merged")
        if short:
            blast_reader_res = blast_reader(blast_file="blast/merged", output=output_file, max_evalue=0.4, format="csv", ancestor_name=ancestor_name, ancestor_rank=ancestor_rank)
        else:
            blast_reader_res = blast_reader(blast_file="blast/merged", output=output_file, min_bitscore=50, format="csv", ancestor_name=ancestor_name, ancestor_rank=ancestor_rank)
        if not os.path.exists(blast_reader_res):
            return "NOMATCH"
        testIsEmpty = open(blast_reader_res, 'r')
        if (testIsEmpty.readlines()==[]):
            testIsEmpty.close()
            return "NOMATCH"
        testIsEmpty.close()
        clear()
        return blast_reader_res
       
        
def fasta_split(file_path, dir, cpus):
    # Open the FASTA file
    fasta_records = SeqIO.parse(file_path, 'fasta')
    fasta_records = sorted(fasta_records, key=lambda x: len(x.seq), reverse=True)
    if os.path.exists(dir):
        for filename in os.listdir(dir):
            os.remove(f"{dir}/{filename}")
    else:
        os.makedirs(dir)
    
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
        file_name = dir + f"/file_{i+1}.fasta"
        SeqIO.write(record_list, file_name, 'fasta')
        file_names.append(file_name)
    
    return file_names

def run_blast(protein_file, db_name, i):
    out = f"blast/blast_{i}"
    command = f"blastp -query {protein_file} -db {db_name} -out {out} -evalue 10"
    print(f" Run {command} ...")
    subprocess.run(command, shell=True, check=True)
    return out
    
def make_blast_db(file):
    db_name, extension = os.path.splitext(os.path.basename(file))
    db_name = "database/"+db_name
    
    if os.path.exists(db_name + ".phr") and os.path.exists(db_name + ".pin") and os.path.exists(db_name + ".psq"):
        return db_name
    else:
        command = "makeblastdb -dbtype prot -in \"\\\""+file+"\\\"\" -out "+db_name
        print(f" Run {command} ...")
        subprocess.run(command, shell=True, check=True)
        return db_name    

def concatenate_files(input_files, output_file):
    with open(output_file, 'w') as outfile:
        for infile in input_files:
            with open(infile, 'r') as infile_handle:
                outfile.write(infile_handle.read())
    return output_file


def clear():
    for filename in os.listdir("blast"):
        if os.path.isfile(f"blast/{filename}"):
            os.remove(f"blast/{filename}")

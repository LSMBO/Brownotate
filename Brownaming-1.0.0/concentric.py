import os
import table
from Bio import SeqIO
import re

def concentric(blast_reader_files, fasta_file, out_blast, out_stats, out_id_map, out_fasta):
    os.remove(out_blast) if os.path.exists(out_blast) else None
    os.remove(out_stats) if os.path.exists(out_stats) else None
    os.remove(out_id_map) if os.path.exists(out_id_map) else None
    os.remove(out_fasta) if os.path.exists(out_fasta) else None
    
    result_hashmap = {}
    for record in SeqIO.parse(fasta_file, "fasta"):
        result_hashmap[record.id]=[]

    for blast_reader in blast_reader_files:
        blast_reader = table.csv_to_table(blast_reader, True)
        for line in blast_reader:
            query_accession = line[0]
            if (len(result_hashmap[query_accession])!=3):
                match = line[2:-2]
                if (len(result_hashmap[query_accession])==0):
                    match.append("True")
                else:
                    match.append("False")
                result_hashmap[query_accession].append(match)

    output_tab = [["Query accession", "Subject accession", "Subject description", "Species", "Common Ancestor name", "Common Ancestor rank", "Gene name", "Bitscore", "Evalue", "Identity", "Similarity", "Best hit"]] 
    for query, match in result_hashmap.items():
        for m in match:
            line = [query]  
            for elt in m:
                line.append(str(elt))
            output_tab.append(line)

    table.create_xlsx(output_tab, out_blast)
    score = create_fasta(fasta_file, output_tab, out_fasta, out_id_map)
    score_percentage = (score[0]/score[1])*100
    with open(out_stats, "w") as f:
        f.write(f" {str(score[0])} of the {str(score[1])} queries have been annotated ({round(score_percentage, 2)}% )")


def create_fasta(originalFasta, listToConvert, name, out_id_map):
    corresTab = [["Old accession", "New accession", "Has been annotated ?"]]
    numOfAnnotated = 0
    totalNumOfQueries = 0
    cpt = 1
    outputFasta = open(name, "a")
    for record in SeqIO.parse(originalFasta, "fasta"):
        totalNumOfQueries = totalNumOfQueries + 1
        oldID = record.id
        newID = generateID(cpt)
        newDescription = "Uncharacterized protein"
        cpt = cpt+1 
        for res in listToConvert:
            if (res[0] == oldID):
                if (res[-1]=="True"):
                    rawDes_re = re.findall(r" .* OS=", res[2])
                    if (len(rawDes_re)!=0): # -> Uniprot match
                        rawDes = rawDes_re[0]
                        newDescription = rawDes[1:-4] + " FROM "+res[3]
                    else:
                        rawDes_re = re.findall(r" \[.+\]", res[2])
                        if (len(rawDes_re)!=0): # -> NCBI match
                            rawDes = re.search(r'(?<=\d\s)(.*?)(?=\s\[\w+\s\w+\]$)', res[2]).group(0)
                            newDescription = rawDes + " FROM "+rawDes_re[0][2:-1]
        if (newDescription == "Uncharacterized protein"):
            corresTab.append([oldID, newID, "NO"])     
        else:
            corresTab.append([oldID, newID, "YES"])
            numOfAnnotated = numOfAnnotated + 1
        record.id = newID
        record.description = newID + " " + newDescription
        SeqIO.write(record, outputFasta, "fasta")
    outputFasta.close()
    table.create_xlsx(corresTab, out_id_map)
    return [numOfAnnotated,totalNumOfQueries]

def generateID(num):
    numLen = len(str(num))
    idString = ""
    for i in range(6-numLen):
        idString = idString + "0" 
    return "br_" + idString + str(num)
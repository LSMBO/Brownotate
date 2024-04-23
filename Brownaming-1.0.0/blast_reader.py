import os
import re
from Bio import SeqIO
import table

def blast_reader(blast_file, min_bitscore=0, max_evalue=10000, min_identity=0, min_similarity=0, top=3, output=None, format="xlsx"):
    if not output:
        output = "Blast_reader_on_"+os.path.basename(blast_file)
    blast_tab = fileToTab(blast_file)
    
    OUTPUT_TAB_HEADER = ["Query accession", "Query description", "Subject accession", "Subject description", "Species", "Gene name", "Bitscore", "Evalue", "Identity", "Similarity", "Start", "Stop"]
    OUTPUT_TAB = get_table(blast_tab, min_bitscore, max_evalue, min_identity, min_similarity, top)
    OUTPUT_TAB.insert(0, OUTPUT_TAB_HEADER)
    
    if os.path.exists(output):
        os.remove(output)
        
    if (format=="xlsx"):
        output = table.create_xlsx(OUTPUT_TAB, output)
        
    else:
        output = table.create_csv(OUTPUT_TAB, output)
        
    return output

def get_table(blast_tab, min_bitscore, max_evalue, min_identity, min_similarity, top):
    tab = []
    for i in range(len(blast_tab)):
        line = blast_tab[i]
        
        if line.startswith("Query="):
            query_accession = re.findall(r"^[^ ]*", line[7:])[0]
            query_description = line[7:]
            cur_top = 1
            
        elif line.startswith(">") and cur_top <= top:
            cur_top += 1
            
            subject = line[1:]
            j = 1
            
            while blast_tab[i+j][:7] != "Length=":
                subject += blast_tab[i+j]
                j += 1
                
            subject_accession = re.findall(r"^[^ ]*", subject)[0]
            
            rawSpecies = re.findall(r"OS=.*OX=", subject)
            species = rawSpecies[0][3:-4] if rawSpecies else ""
            
            rawGeneName = re.findall(r"GN=[^ ]*", subject)
            gene_name = rawGeneName[0][3:] if rawGeneName else ""
            
            j=j+2

            rawBitscore = re.findall(r"\d+\.?\d bits", blast_tab[i+j])[0]
            bitscore = float(rawBitscore[:-5])
            
            rawEvalue = re.findall(r"Expect = .+\,", blast_tab[i+j])[0]
            evalue = float(rawEvalue[9:-1])

            identityRaw = re.findall(r"Identities[^\,]*", blast_tab[i+j+1])
            identity = float(re.findall(r"\(.*", identityRaw[0])[0][1:-2]) if identityRaw else ""

            similarityRaw = re.findall(r"Positives[^\,]*", blast_tab[i+j+1])
            similarity = float(re.findall(r"\(.*", similarityRaw[0])[0][1:-2]) if similarityRaw else ""

            alignementStartLine = i+j+5
            subjectStartStop = getStartStop(alignementStartLine, blast_tab)
            start = subjectStartStop[0]
            stop = subjectStartStop[1]

            if (evalue <= max_evalue 
                    and bitscore >= min_bitscore
                    and identity >= min_identity
                    and similarity >= min_similarity
                    and all(x not in subject for x in ["Uncharacterized", "uncharacterized", "---NA", "Hypothetical", "hypothetical", "PREDICTED:"])
                    and subject != "Partial"):
                
                tab.append([query_accession, query_description, subject_accession, subject, species, gene_name, bitscore, evalue, identity, similarity, start, stop])
    return tab

def fileToTab(file):
    tab = []
    with open(file, 'r') as blastfile:
        lines = blastfile.readlines()
        for i in range(len(lines)):
            tab.append(lines[i][:-1])
    return tab

def getStartStop(lineNum, blast_tab):
        line1 = blast_tab[lineNum]
        rawStart = re.findall(r"^Sbjct[^[A-Z]*", line1)[0][5:]
        start = rawStart.replace(' ', '')
        stopLine = blast_tab[lineNum]
        i = lineNum + 4
        while (blast_tab[i][:5]=="Sbjct"):
                stopLine = blast_tab[i]
                i = i + 4
        rawStop = re.findall(r" \d*", stopLine)[-1]
        stop = rawStop.replace(' ', '')
        return [start, stop]
    

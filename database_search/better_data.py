from . import uniprot

def betterData(search_data_res):
    if 'genome' in search_data_res:
        if search_data_res["genome"]["ensembl"]:
            ensembl_data = search_data_res["genome"]["ensembl"]
            if ensembl_data["url"]:
                return ensembl_data
        if search_data_res["genome"]["refseq"]:
            refseq_data = search_data_res["genome"]["refseq"]
            if (refseq_data["url"]):
                return refseq_data
        if search_data_res["genome"]["genbank"]:
            genbank_data = search_data_res["genome"]["genbank"]            
            if (genbank_data["url"]):
                return genbank_data
    if 'dnaseq' in search_data_res:
        dnaseq_data = search_data_res["dnaseq"]
        if (len(dnaseq_data)!=0):
            return dnaseq_data

    return {}

def betterEvidence(evidence, my_taxo):
    ensembl_evidence_score = -1

    if evidence["ensembl"]:
        ensembl_evidence = evidence["ensembl"]
        ensembl_evidence_score = getEvidenceScore(ensembl_evidence, my_taxo)
    uniprot_evidence = evidence["uniprot"]   
    uniprot_evidence_score = getEvidenceScore(uniprot_evidence, my_taxo)
    refseq_evidence = evidence["refseq"]
    refseq_evidence_score = getEvidenceScore(refseq_evidence, my_taxo)
    genbank_evidence = evidence["genbank"]
    genbank_evidence_score = getEvidenceScore(genbank_evidence, my_taxo)

    # Compare les scores et retourne la meilleure evidence
    best_evidence = None
    best_score = -1
    if ensembl_evidence_score > best_score:
        best_evidence = ensembl_evidence
        best_score = ensembl_evidence_score
    if uniprot_evidence_score > best_score:
        best_evidence = uniprot_evidence
        best_score = uniprot_evidence_score
    if refseq_evidence_score > best_score:
        best_evidence = refseq_evidence
        best_score = refseq_evidence_score
    if genbank_evidence_score > best_score:
        best_evidence = genbank_evidence
        best_score = genbank_evidence_score
 
    return best_evidence


def getEvidenceScore(evidence, my_taxo):
    evidence_taxon_id = evidence["taxonId"]
    my_taxo_id = my_taxo["taxonId"]
    
    # Set the initial score
    score = 100
    
    # Check if the evidence and my_taxo are the same species
    if (evidence_taxon_id == my_taxo_id):
        # If they are the same, return a perfect score
        return score
    
    evidence_taxon = uniprot.taxo(evidence_taxon_id)
    
    # Get the lineage (list of taxonIDs from species to kingdom) for the evidence and my_taxo
    evidence_lineage = [item["taxonId"] for item in evidence_taxon["lineage"]]
    my_taxo_lineage = [item["taxonId"] for item in my_taxo["lineage"]]
    
    # Set the initial penalty
    initial_penalty = 5
    
    # Check how far apart the two lineages are by iterating over the evidence lineage
    for id in evidence_lineage:
        if (id in my_taxo_lineage):
            # If the current id is in the my_taxo lineage, return the current score minus the penalty
            return score - initial_penalty
        else:
            # If the current id is not in the my_taxo lineage, increase the penalty
            initial_penalty += 2
            
    return 0


            

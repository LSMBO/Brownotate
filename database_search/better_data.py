from database_search.uniprot import UniprotTaxo

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

def betterEvidence(evidence, taxo):
    ensembl_evidence_score = -1
    if evidence["ensembl"]:
        ensembl_evidence = evidence["ensembl"]
        ensembl_evidence_score = getEvidenceScore(ensembl_evidence, taxo)
    uniprot_proteome_evidence = evidence["uniprot_proteome"]   
    uniprot_proteome_evidence_score = getEvidenceScore(uniprot_proteome_evidence, taxo)
    refseq_evidence = evidence["refseq"]
    refseq_evidence_score = getEvidenceScore(refseq_evidence, taxo)
    genbank_evidence = evidence["genbank"]
    genbank_evidence_score = getEvidenceScore(genbank_evidence, taxo)

    best_evidence = None
    best_score = -1
    if ensembl_evidence_score > best_score:
        best_evidence = ensembl_evidence
        best_score = ensembl_evidence_score
    if uniprot_proteome_evidence_score > best_score:
        best_evidence = uniprot_proteome_evidence
        best_score = uniprot_proteome_evidence_score
    if refseq_evidence_score > best_score:
        best_evidence = refseq_evidence
        best_score = refseq_evidence_score
    if genbank_evidence_score > best_score:
        best_evidence = genbank_evidence
        best_score = genbank_evidence_score
 
    return best_evidence

def getEvidenceScore(evidence, taxo):
    evidence_taxon_id = evidence["taxonId"]
    taxo_id = taxo["taxonId"]
    score = 100

    if (int(evidence_taxon_id) == taxo_id):
        return score
    
    evidence_taxon = UniprotTaxo(evidence_taxon_id)
    evidence_lineage = [item["taxonId"] for item in evidence_taxon.taxonomy["lineage"]]
    taxo_lineage = [item["taxonId"] for item in taxo["lineage"]]
    initial_penalty = 1
    
    # Check how far apart the two lineages are by iterating over the evidence lineage
    for id in evidence_lineage:
        if (id in taxo_lineage):
            return score - initial_penalty
        else:
            initial_penalty += 1
    return 0


            

def run_get_sra_entries(state, database_search):
    accessions = state["args"]["dna_sra"]
    sra_entries = database_search.getSequencing('DNA', accessions, state["config"])
    for i in range(len(accessions)):
        if sra_entries['runs'][i] == 'Nothing':
            raise ValueError(f"\nThe SRA accession {accessions[i]} has not been found in the SRA database. Please try to download it manually or use another one.")
    return database_search.getSequencing('DNA', accessions, state["config"])
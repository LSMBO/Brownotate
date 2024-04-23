def run_bowtie2(state, sequencing):
    sequencing_files = state["dnaseq_files"]
    if "fastp_files" in state:
        sequencing_files = state["fastp_files"]

    return sequencing.filter_phix_files(sequencing_files, state)
    
    
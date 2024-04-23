def run_megahit(state, sequencing):
    sequencing_files = state["dnaseq_files"]
    if "fastp_files" in state:
        sequencing_files = state["fastp_files"]
    if "phix_files" in state:
        sequencing_files = state["phix_files"]
    return sequencing.megahit(state["scientific_name"], sequencing_files, state["args"]["cpus"], state["run_id"])
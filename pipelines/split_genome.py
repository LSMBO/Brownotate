def run_split_genome(state, annotation):
    return annotation.fasta_split(state['genome_file'], state['args']['cpus'])
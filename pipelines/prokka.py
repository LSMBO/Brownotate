def run_prokka(state, annotation):
    return annotation.prokka(state['genome_file'], state['args']['cpus'])
    
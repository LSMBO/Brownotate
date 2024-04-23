def run_busco(state, stats, mode):
    if mode == 'genome':
        stats.busco(input_file=state['genome_file'], taxo=state['taxo'], mode=mode, cpus=state['args']['cpus'])
    else:
        stats.busco(input_file=state['annotation'], taxo=state['taxo'], mode=mode, cpus=state['args']['cpus'])
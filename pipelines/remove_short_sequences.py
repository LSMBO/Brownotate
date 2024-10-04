def run_remove_short_sequences(state, annotation):
    return annotation.remove_short_sequences(state['annotation'], state['args']["min_length"])


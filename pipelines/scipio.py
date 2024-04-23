import os

def run_scipio(state, annotation, flex):
    return annotation.scipio(state['subgenomes'], os.path.abspath(state['evidence_file']), flex)
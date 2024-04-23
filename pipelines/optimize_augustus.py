def run_optimize_augustus(state, annotation):
    if "num_genes_v2" in state:
        annotation.optimize_model(state['num_genes_v2'])
    else:
        annotation.optimize_model(state["num_genes"])
    return True
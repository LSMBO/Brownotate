def run_get_evidence(state, database_search):
    entries = database_search.evidence(state["scientific_name"], state["taxo"])
    return database_search.betterEvidence(entries, state["taxo"])
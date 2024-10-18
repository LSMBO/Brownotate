def run_get_evidence(state, database_search):
	synonyms_scientific_names = [state['scientific_name']]
	if 'synonyms' in state['taxo'].keys():
		synonyms_scientific_names += state['taxo']['synonyms']
	entries = database_search.proteins(synonyms_scientific_names, state["taxo"], search_similar_species=True, config=state['config'])
	return database_search.betterEvidence(entries, state["taxo"])
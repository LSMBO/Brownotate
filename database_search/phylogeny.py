from database_search.uniprot import UniprotTaxo
import matplotlib.pyplot as plt
from flask import Blueprint, request, jsonify
from flask_app.database import find, update_one
import json, os
from timer import timer

dbs_phylogeny_bp = Blueprint('dbs_phylogeny_bp', __name__)

@dbs_phylogeny_bp.route('/dbs_phylogeny', methods=['POST'])
def dbs_phylogeny():
    start_time = timer.start()
    
    user = request.json.get('user')
    dbsearch = request.json.get('dbsearch')
    create_new_dbs = request.json.get('createNewDBS')

    if not user or not dbsearch:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    output_data = {
        'run_id': dbsearch['run_id'],
        'status': 'phylogeny',
        'date': dbsearch['date'],
        'data': dbsearch['data']
    }

    phylogeny_map_path = os.path.join('output_runs', dbsearch['run_id'], 'phylogeny_map.png')
    get_phylogeny_map(dbsearch['data'], phylogeny_map_path)
    output_data['data']['phylogeny_map'] = phylogeny_map_path

    timer_str = timer.stop(start_time)
    print(f"Timer dbs_phylogeny: {timer_str}")
    output_data['data']['timer_phylogeny'] = timer_str
    
    query = {'run_id': dbsearch['run_id']}
    update = { '$set': {'status': 'phylogeny', 'data': output_data['data']} }    
    
    if create_new_dbs:
        update_one('dbsearch', query, update)
    
    return jsonify(output_data)




def extract_all_taxids(dbsearch):
    taxid_fields = [
        'uniprot_proteomes',
        'ncbi_refseq_annotated_genomes',
        'ncbi_genbank_annotated_genomes',
        'ncbi_refseq_genomes',
        'ncbi_genbank_genomes',
        'ensembl_annotated_genomes',
        'ensembl_genomes'
    ]
    list_of_taxid = []
    for field in taxid_fields:
        for entry in dbsearch.get(field, []):
            list_of_taxid.append(entry['taxid'])
    for batch in dbsearch.get('dnaseq', []):
        list_of_taxid.append(int(batch['runs'][0]['taxid']))
    return list(set(list_of_taxid))

def get_lineages(list_of_taxid, main_taxid):
    list_of_lineage = []
    for taxid in list_of_taxid:
        if taxid != main_taxid:
            taxo = UniprotTaxo(taxid, main_taxid)
            if taxo:
                list_of_lineage.append(taxo.taxonomy['lineage'])
    return list_of_lineage

def extract_main_lineage_info(main_lineage):
    taxids = []
    names = []
    ranks = []
    for entry in main_lineage:
        taxids.append(entry['taxonId'])
        names.append(entry['scientificName'])
        ranks.append(entry['rank'])
            
    main_lineage_string = f"{names[0]} ({ranks[0]}) TaxID: {taxids[0]}"
    return taxids, names, ranks, main_lineage_string

def extract_lineage_info(lineage):
    taxids = []
    names = []
    ranks = []
    for entry in lineage:
        taxids.append(entry['taxonId'])
        names.append(entry['scientificName'])
        ranks.append(entry['rank'])
            
    lineage_string = f"{names[0]} ({ranks[0]}) TaxID: {taxids[0]}"
    return taxids, names, ranks, lineage_string


def plot_lineages(ax, list_of_lineage, main_lineage_taxids, main_lineage_scientific_names, main_lineage_ranks, ylim):
    intersection_indexes = []
    for lineage in list_of_lineage:
        lineage_taxids, lineage_scientific_names, lineage_ranks, taxo_string = extract_lineage_info(lineage)
        intersection_index = get_phylogeny_intersection(lineage_taxids, main_lineage_taxids)
        intersection_indexes.append(intersection_index)
        if intersection_index:
            x_lineage = [intersection_index, 0]
            y_lineage = [intersection_index, 2 * intersection_index]
            ax.plot(x_lineage, y_lineage, linestyle='-', color='green', marker='o')
            if ylim < (2 * intersection_index) + 1:
                ylim = (2 * intersection_index) + 1
            for j, (name, rank, taxid) in enumerate(zip(main_lineage_scientific_names, main_lineage_ranks, main_lineage_taxids)):
                if j == intersection_index:
                    ax.text(
                        j + 0.2, 
                        j - 0.4, 
                        f"{name} ({rank}) TaxID: {taxid}", fontsize=8, color='green', ha='left'
                    )
                    y_offset = 0.6 * (intersection_indexes.count(intersection_index)) - 0.6
                    ax.text(
                        -0.2,
                        y_offset + (2 * intersection_index), 
                        taxo_string, fontsize=8, color='green', ha='right'
                    )
                    break
        else:
            # The 'lineage' taxo is a descendant of the main lineage (ie it's a strain and the main lineage is the species)
            y_offset = -0.6 * (intersection_indexes.count(intersection_index)) + 0.6
            ax.text(
                -0.2,
                y_offset - 0.2, 
                taxo_string, fontsize=8, color='green', ha='right'
            )
    return ylim

def plot_main_taxonomy(ax, main_lineage_string):
    ax.plot(0, 0, linestyle='-', color='blue', marker='o')
    ax.text(
        0.2, 
        -0.4, 
        main_lineage_string, 
        fontsize=8, color='blue', ha='left', fontweight='bold'
    )

def finalize_plot(ax, main_lineage_taxids, ylim):
    ax.set_xlim(-1, len(main_lineage_taxids) + 1)
    ax.set_ylim(-1, ylim)
    ax.axis('off')
    ax.legend([
            plt.Line2D([0], [0], color='green', marker='o', linestyle='-'),
            plt.Line2D([0], [0], color='blue', marker='o', linestyle='-')
        ], 
        ["Taxonomies found during the database search", "Queried Taxonomy"],
        loc='lower right', fontsize=8)

def get_phylogeny_intersection(lineage1, lineage2):
    for taxid in lineage1:
        if taxid in lineage2:
            return lineage2.index(taxid)
    return None

def get_phylogeny_map(dbsearch, output_path):
    main_lineage = dbsearch['taxonomy']['lineage']
    main_taxid = dbsearch['taxonomy']['taxonId']
    list_of_taxid = extract_all_taxids(dbsearch)
    list_of_lineage = get_lineages(list_of_taxid, main_taxid)

    fig, ax = plt.subplots(figsize=(10, 5))
    main_lineage_taxids, main_lineage_scientific_names, main_lineage_ranks, main_lineage_string = extract_lineage_info(main_lineage)
    ylim = len(main_lineage_taxids)
    y_main = range(len(main_lineage_taxids))
    x_main = range(len(main_lineage_taxids))

    # plot main lineage
    ax.plot(x_main, y_main, linestyle='-', color='black', marker='o')

    # plot other taxonomies
    ylim = plot_lineages(ax, list_of_lineage, main_lineage_taxids, main_lineage_scientific_names, main_lineage_ranks, ylim)

    plot_main_taxonomy(ax, main_lineage_string)
    finalize_plot(ax, main_lineage_taxids, ylim)

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    return 'phylogeny_map.png'


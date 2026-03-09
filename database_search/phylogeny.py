from database_search.uniprot_taxo import UniprotTaxo
import matplotlib.pyplot as plt
from flask import Blueprint, request, jsonify
import json, os, datetime
from timer import timer

dbs_phylogeny_bp = Blueprint('dbs_phylogeny_bp', __name__)

@dbs_phylogeny_bp.route('/dbs_phylogeny', methods=['POST'])
def dbs_phylogeny():
    try:
        start_time = timer.start()
        user = request.json.get('user')
        dbs = request.json.get('dbs')
        taxonomy = request.json.get('taxonomy')
        current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")
        if not user or not dbs or not taxonomy:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

        # Clean up old phylogeny maps (older than 7 days)
        phylogeny_maps_dir = os.path.join('output_runs', 'phylogeny_maps')
        os.makedirs(phylogeny_maps_dir, exist_ok=True)
        
        cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=4) # days=7
        for filename in os.listdir(phylogeny_maps_dir):
            file_path = os.path.join(phylogeny_maps_dir, filename)
            if os.path.isfile(file_path):
                file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < cutoff_time:
                    os.remove(file_path)
            
        phylogeny_map_path = os.path.join(phylogeny_maps_dir, f'phylogeny_map_{current_datetime}.png')
        get_phylogeny_map(dbs, taxonomy, phylogeny_map_path)
        timer_str = timer.stop(start_time)

        response_data = {
            'user': user, 
            'timer': timer_str,
            'date': current_datetime,
            'scientific_name': taxonomy['scientificName'],
            'taxid': taxonomy['taxonId'],
            'data': {
                'phylogeny_map': phylogeny_map_path
            }
        }
        
        return jsonify({'status': 'success', 'data': response_data}), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred',
            'timer': timer.stop(start_time),
            'details': str(e)
        }), 500    


def extract_all_taxids(dbs):
    list_of_taxid = []
    
    # Uniprot proteome
    if dbs.get('uniprot_proteome') and dbs['uniprot_proteome'].get('proteins'):
        for proteome in dbs['uniprot_proteome']['proteins']:
            if 'taxid' in proteome:
                list_of_taxid.append(proteome['taxid'])
    
    # Ensembl proteins and assemblies
    if dbs.get('ensembl'):
        if dbs['ensembl'].get('proteins'):
            for entry in dbs['ensembl']['proteins']:
                if 'taxid' in entry:
                    list_of_taxid.append(entry['taxid'])
        if dbs['ensembl'].get('assemblies'):
            for entry in dbs['ensembl']['assemblies']:
                if 'taxid' in entry:
                    list_of_taxid.append(entry['taxid'])
    
    # RefSeq proteins and assemblies
    if dbs.get('refseq'):
        if dbs['refseq'].get('proteins'):
            for entry in dbs['refseq']['proteins']:
                if 'taxid' in entry:
                    list_of_taxid.append(entry['taxid'])
        if dbs['refseq'].get('assemblies'):
            for entry in dbs['refseq']['assemblies']:
                if 'taxid' in entry:
                    list_of_taxid.append(entry['taxid'])
    
    # GenBank proteins and assemblies
    if dbs.get('genbank'):
        if dbs['genbank'].get('proteins'):
            for entry in dbs['genbank']['proteins']:
                if 'taxid' in entry:
                    list_of_taxid.append(entry['taxid'])
        if dbs['genbank'].get('assemblies'):
            for entry in dbs['genbank']['assemblies']:
                if 'taxid' in entry:
                    list_of_taxid.append(entry['taxid'])
    
    # DNA sequencing batches
    if dbs.get('dnaseq') and dbs['dnaseq'].get('batches'):
        for batch in dbs['dnaseq']['batches']:
            if batch.get('runs') and len(batch['runs']) > 0:
                if 'taxid' in batch['runs'][0]:
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

def get_phylogeny_map(dbs, taxonomy, output_path):
    main_lineage = taxonomy['lineage']
    main_taxid = taxonomy['taxonId']
    list_of_taxid = extract_all_taxids(dbs)
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


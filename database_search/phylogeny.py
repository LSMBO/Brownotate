from database_search.uniprot_taxo import UniprotTaxo
from flask import Blueprint, request, jsonify
import datetime
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

        phylogeny_data = build_phylogeny_data(dbs, taxonomy)
        timer_str = timer.stop(start_time)

        return jsonify({
            'status': 'success',
            'data': {
                'user': user,
                'timer': timer_str,
                'date': current_datetime,
                'scientific_name': taxonomy['scientificName'],
                'taxid': taxonomy['taxonId'],
                'data': {
                    'phylogeny': phylogeny_data
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred',
            'details': str(e)
        }), 500


def extract_taxids_by_source(dbs):
    # Returns list of dict entries with taxid/source and optional display metadata.
    result = []
    if dbs.get('uniprot_trembl'):
        result.append({
            'taxid': int(dbs.get('uniprot_trembl')['taxid']),
            'source': 'uniprot_trembl',
            'scientificName': dbs.get('uniprot_trembl').get('scientific_name')
        })
    if dbs.get('uniprot_swissprot'):
        result.append({
            'taxid': int(dbs.get('uniprot_swissprot')['taxid']),
            'source': 'uniprot_swissprot',
            'scientificName': dbs.get('uniprot_swissprot').get('scientific_name')
        })

    if dbs.get('uniprot_proteome'):
        for p in dbs['uniprot_proteome']:
            if 'taxid' in p:
                result.append({
                    'taxid': int(p['taxid']),
                    'source': 'uniprot_proteome',
                    'scientificName': p.get('scientific_name')
                })

    if dbs.get('ensembl'):
        for p in dbs['ensembl'].get('proteins', []):
            if 'taxid' in p:
                result.append({
                    'taxid': int(p['taxid']),
                    'source': 'ensembl_proteins',
                    'scientificName': p.get('scientific_name')
                })
        for a in dbs['ensembl'].get('assemblies', []):
            if 'taxid' in a:
                result.append({
                    'taxid': int(a['taxid']),
                    'source': 'ensembl_assemblies',
                    'scientificName': a.get('scientific_name')
                })

    if dbs.get('refseq'):
        for p in dbs['refseq'].get('proteins', []):
            if 'taxid' in p:
                result.append({
                    'taxid': int(p['taxid']),
                    'source': 'refseq_proteins',
                    'scientificName': p.get('scientific_name')
                })
        for a in dbs['refseq'].get('assemblies', []):
            if 'taxid' in a:
                result.append({
                    'taxid': int(a['taxid']),
                    'source': 'refseq_assemblies',
                    'scientificName': a.get('scientific_name')
                })

    if dbs.get('genbank'):
        for p in dbs['genbank'].get('proteins', []):
            if 'taxid' in p:
                result.append({
                    'taxid': int(p['taxid']),
                    'source': 'genbank_proteins',
                    'scientificName': p.get('scientific_name')
                })
        for a in dbs['genbank'].get('assemblies', []):
            if 'taxid' in a:
                result.append({
                    'taxid': int(a['taxid']),
                    'source': 'genbank_assemblies',
                    'scientificName': a.get('scientific_name')
                })

    if dbs.get('dnaseq'):
        for batch in dbs['dnaseq'].get('batches', []):
            if batch.get('runs') and batch['runs'][0].get('taxid'):
                result.append({
                    'taxid': int(batch['runs'][0]['taxid']),
                    'source': 'dnaseq',
                    'scientificName': batch['runs'][0].get('scientific_name')
                })

    if dbs.get('rnaseq'):
        for batch in dbs['rnaseq'].get('batches', []):
            if batch.get('runs') and batch['runs'][0].get('taxid'):
                result.append({
                    'taxid': int(batch['runs'][0]['taxid']),
                    'source': 'rnaseq',
                    'scientificName': batch['runs'][0].get('scientific_name')
                })

    return result


def _normalize_main_lineage(main_taxid, main_scientific_name, main_lineage):
    normalized = []
    seen = set()
    for entry in main_lineage or []:
        taxid = entry.get('taxonId')
        if taxid is None:
            continue
        taxid = int(taxid)
        if taxid in seen:
            continue
        seen.add(taxid)
        normalized.append({
            'taxonId': taxid,
            'scientificName': entry.get('scientificName', str(taxid)),
            'rank': entry.get('rank', '')
        })

    # Keep queried taxon in the displayed lineage for stable descendant mapping.
    if main_taxid not in seen:
        normalized.insert(0, {
            'taxonId': main_taxid,
            'scientificName': main_scientific_name or str(main_taxid),
            'rank': 'species'
        })

    return normalized


def _best_common_index(lineage_taxids, main_lineage_taxids, main_taxid):
    lineage_set = set(int(t) for t in lineage_taxids if t is not None)
    common = [i for i, t in enumerate(main_lineage_taxids) if t in lineage_set]
    if not common:
        return None

    try:
        main_index = main_lineage_taxids.index(main_taxid)
    except ValueError:
        main_index = 0

    # Pick the closest common ancestor/descendant node to the queried taxon.
    return min(common, key=lambda idx: abs(idx - main_index))


def build_phylogeny_data(dbs, taxonomy):
    main_taxid = int(taxonomy['taxonId'])
    main_lineage = _normalize_main_lineage(main_taxid, taxonomy.get('scientificName'), taxonomy.get('lineage'))
    main_lineage_taxids = [e['taxonId'] for e in main_lineage]

    # Initialize nodes dict with all mainLineage indices
    nodes = {i: [] for i in range(len(main_lineage))}

    taxid_source_pairs = extract_taxids_by_source(dbs)

    # Use set to track unique combinations to avoid duplicates
    seen = set()

    # For each taxid/source entry, find where it belongs.
    for entry in taxid_source_pairs:
        taxid = entry['taxid']
        source = entry['source']

        taxo = UniprotTaxo(taxid, main_taxid)
        taxonomy_data = taxo.taxonomy if taxo and taxo.taxonomy else None

        if taxonomy_data and taxonomy_data.get('lineage'):
            lineage = taxonomy_data['lineage']
            lineage_taxids = [int(e['taxonId']) for e in lineage if e.get('taxonId') is not None]
            intersection_index = _best_common_index(lineage_taxids, main_lineage_taxids, main_taxid)
        else:
            lineage = []
            intersection_index = None

        # If no intersection found, anchor to queried taxon node so children/unknown taxa are still visible.
        if intersection_index is None:
            intersection_index = main_lineage_taxids.index(main_taxid) if main_taxid in main_lineage_taxids else 0
        
        # Create unique key to avoid duplicates
        key = (taxid, source, intersection_index)
        if key in seen:
            continue
        seen.add(key)
        
        scientific_name = entry.get('scientificName')
        rank = ''
        if taxonomy_data:
            scientific_name = taxonomy_data.get('scientificName') or scientific_name
            rank = taxonomy_data.get('rank', '')

        # Add entry to the appropriate node
        nodes[intersection_index].append({
            'taxid': taxid,
            'scientificName': scientific_name or str(taxid),
            'rank': rank,
            'source': source
        })

    return {'mainLineage': main_lineage, 'nodes': nodes}


import json
import os
import re
import subprocess
from datetime import datetime

from flask_app.utils import load_config


def _first_non_empty_line(text):
    for line in (text or '').splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _run_cmd(args, env, cwd):
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            cwd=cwd,
            check=False,
        )
        line = _first_non_empty_line(proc.stdout) or _first_non_empty_line(proc.stderr)
        if not line:
            return None
        return line
    except Exception:
        return None


def _normalize_version_text(value):
    text = str(value or '').strip()
    if not text:
        return 'not available'

    lowered = text.lower()
    if lowered in {'not run', 'not available'}:
        return lowered

    match = re.search(r'\((\d+(?:\.\d+)+)\)', text)
    if not match:
        match = re.search(r'\bv(?:ersion)?\s*[:=]?\s*(\d+(?:\.\d+)+)\b', text, re.IGNORECASE)
    if not match:
        match = re.search(r'\b(\d+(?:\.\d+)+)\b', text)

    if match:
        return f"v{match.group(1)}"

    return text


def detect_brownotate_version(repo_root):
    client_package = os.path.abspath(os.path.join(repo_root, '..', 'brownotate-app-latest', 'package.json'))
    if os.path.exists(client_package):
        try:
            with open(client_package, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if data.get('version'):
                return str(data['version'])
        except Exception:
            pass

    version_file = os.path.join(repo_root, 'VERSION')
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r', encoding='utf-8') as fh:
                value = fh.read().strip()
                if value:
                    return value
        except OSError:
            pass

    cfg_file = os.path.join(repo_root, 'config.json')
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if data.get('BROWNOTATE_VERSION'):
                return str(data['BROWNOTATE_VERSION'])
        except Exception:
            pass

    git_ver = _run_cmd(['git', 'describe', '--tags', '--always'], os.environ.copy(), repo_root)
    if git_ver:
        return git_ver

    return 'unknown'


def detect_tool_versions(parameters):
    cfg = load_config()
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    env = os.environ.copy()
    env['PATH'] = os.path.join(cfg['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env.get('PATH', '')

    tools = {
        'blat': [['blat', '-version']],
        'scipio': [['scipio', '--version']],
        'augustus': [['augustus', '--version']],
        'prokka': [['prokka', '--version']],
        'busco': [['busco', '--version']],
        'fastp': [['fastp', '--version']],
        'canu': [['canu', '--version']],
        'canu_docker': [['docker', 'run', '--rm', 'quay.io/biocontainers/canu:2.2--ha47f30e_0', 'canu', '--version']],
        'megahit': [['megahit', '--version']],
        'transdecoder': [['TransDecoder.LongOrfs', '--version']],
        'trinity': [['Trinity', '--version']],
        'rnabloom': [['rnabloom', '--version'], ['RNA-Bloom', '--version']],
        'cd_hit': [['cd-hit', '-h']],
        'bowtie2': [['bowtie2', '--version']],
    }

    section_start = parameters.get('startSection', {}) if isinstance(parameters, dict) else {}
    run_type = str(parameters.get('type') or '').strip().lower()
    is_functional_run = run_type == 'functional'
    assembly_section = parameters.get('assemblySection', {}) if isinstance(parameters, dict) else {}
    busco_section = parameters.get('buscoSection', {}) if isinstance(parameters, dict) else {}
    brownaming_section = parameters.get('brownamingSection', {}) if isinstance(parameters, dict) else {}
    species = parameters.get('species', {}) if isinstance(parameters, dict) else {}

    used = {
        'blat': (not is_functional_run) and (not species.get('is_bacteria', False)),
        'scipio': (not is_functional_run) and (not species.get('is_bacteria', False)),
        'augustus': (not is_functional_run) and (not species.get('is_bacteria', False)),
        'prokka': (not is_functional_run) and bool(species.get('is_bacteria', False)),
        'busco': (not is_functional_run) and bool(busco_section.get('assembly') or busco_section.get('annotation')),
        'fastp': (not is_functional_run) and bool(assembly_section.get('runFastp')),
        'canu': (not is_functional_run) and bool(assembly_section.get('canu')),
        'canu_docker': (not is_functional_run) and bool(assembly_section.get('canu')),
        'megahit': (not is_functional_run) and bool(assembly_section.get('megahit')),
        'transdecoder': (not is_functional_run) and bool(section_start.get('rnaSequencing')),
        'trinity': (not is_functional_run) and bool(section_start.get('rnaSequencing')),
        'rnabloom': (not is_functional_run) and bool(section_start.get('rnaSequencing')),
        'cd_hit': (not is_functional_run) and bool(parameters.get('annotationSection', {}).get('removeStrict') or parameters.get('annotationSection', {}).get('removeSoft')),
        'bowtie2': (not is_functional_run) and bool(assembly_section.get('runBowtie2')),
        'brownaming': bool(is_functional_run or (not brownaming_section.get('skip', False))),
    }

    known_versions = {
        'blat': 'v35',
        'scipio': 'v1.4.1',
        'trinity': 'v2.15.1',
        'transdecoder': 'v5.7.1',
        'rnabloom': 'v2.0.1',
        'cd_hit': 'v4.8.1',
        'bowtie2': 'v2.5.4',
        'brownaming': _detect_brownaming_version(repo_root) or 'v2.0.0',
    }

    versions = {}
    for tool, command_sets in tools.items():
        if not used.get(tool, True):
            versions[tool] = {
                'used_in_run': False,
                'version': 'not run',
            }
            continue

        version = None
        for command in command_sets:
            version = _run_cmd(command, env, repo_root)
            if version:
                break

        if tool in known_versions:
            version = known_versions[tool]

        if tool == 'canu' and versions.get('canu_docker', {}).get('version'):
            version = versions['canu_docker']['version']

        versions[tool] = {
            'used_in_run': used.get(tool, True),
            'version': _normalize_version_text(version or 'not available'),
        }

    if 'canu_docker' in versions and versions['canu_docker']['version']:
        versions['canu']['version'] = versions['canu_docker']['version']

    versions['brownaming'] = {
        'used_in_run': used.get('brownaming', True),
        'version': _normalize_version_text(known_versions['brownaming']),
    }

    return versions


def _detect_brownaming_version(repo_root):
    readme_path = os.path.join(repo_root, 'Brownaming', 'README.md')
    if not os.path.exists(readme_path):
        return None

    try:
        with open(readme_path, 'r', encoding='utf-8') as fh:
            for line in fh:
                text = line.strip()
                if text.lower().startswith('# brownaming v'):
                    return text.lstrip('#').strip()
    except OSError:
        return None

    return None


def _format_evidence_info(parameters):
    annotation_section = parameters.get('annotationSection', {}) if isinstance(parameters, dict) else {}
    mode = annotation_section.get('evidenceSelectionMode')
    source_files = annotation_section.get('evidenceSourceFiles') or []
    selected_entries = annotation_section.get('selectedEvidenceEntries') or []
    final_file = annotation_section.get('evidenceFileOnServer')

    lines = []
    lines.append(f"Selection mode: {mode or 'unknown'}")
    lines.append(f"Final evidence file: {final_file or 'N/A'}")

    if source_files:
        lines.append('Merged source files:')
        for item in source_files:
            lines.append(f"  - {item}")

    if selected_entries:
        lines.append('Selected evidence entries:')
        for item in selected_entries:
            tax = item.get('taxid', 'NA')
            sci = item.get('scientific_name') or item.get('scientificName') or 'Unknown'
            db = item.get('database', 'Unknown')
            acc = item.get('accession', 'NA')
            lines.append(f"  - {sci} (taxid={tax}) [{db}] accession={acc}")

    return '\n'.join(lines)


def _format_run_entry(run):
    accession = run.get('accession', 'N/A')
    platform = run.get('platform', 'N/A')
    size = run.get('size')
    if isinstance(size, (int, float)):
        return f"{accession} ({platform}) {size:.2f} Gb"
    return f"{accession} ({platform})"


def _append_lines(lines, title, entries):
    lines.append(title)
    lines.append('-' * 80)
    lines.extend(entries)
    lines.append('')


def write_parameters_report(run_data, output_run_path):
    try:
        parameters = run_data.get('parameters', {}) if isinstance(run_data, dict) else {}
        run_id = parameters.get('id')
        species = parameters.get('species', {}) if isinstance(parameters, dict) else {}
        start_section = parameters.get('startSection', {}) if isinstance(parameters, dict) else {}
        assembly_section = parameters.get('assemblySection', {}) if isinstance(parameters, dict) else {}
        annotation_section = parameters.get('annotationSection', {}) if isinstance(parameters, dict) else {}
        brownaming_section = parameters.get('brownamingSection', {}) if isinstance(parameters, dict) else {}
        busco_section = parameters.get('buscoSection', {}) if isinstance(parameters, dict) else {}
        run_type = str(parameters.get('type') or '').strip().lower()
        is_functional_run = run_type == 'functional'
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        brownotate_version = detect_brownotate_version(repo_root)
        tool_versions = detect_tool_versions(parameters)

        lines = []
        lines.append('BROWNOTATE PARAMETERS REPORT')
        lines.append('=' * 80)
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Brownotate version: {brownotate_version}")
        lines.append(f"Run ID: {run_id}")
        lines.append(f"Species: {species.get('scientificName', 'N/A')} (TaxID: {species.get('taxonID', 'N/A')})")
        lines.append('')

        started = []
        is_rna = bool(start_section.get('rnaSequencing'))
        is_dna = bool(start_section.get('sequencing'))

        sequencing_cfg = start_section.get('sequencing') if isinstance(start_section.get('sequencing'), dict) else {}

        if is_functional_run:
            started.append('Mode: Brownaming only')
            protein_file = parameters.get('proteinFileOnServer')
            if isinstance(protein_file, list):
                protein_file = protein_file[0] if protein_file else None
            if not protein_file:
                protein_file = parameters.get('proteinFileAccession')
            started.append(f"Protein file: {protein_file or 'N/A'}")
        elif start_section.get('assembly'):
            started.append('Mode: Assembly')
        elif is_rna:
            started.append('Mode: RNA Sequencing')
        elif is_dna:
            started.append('Mode: DNA Sequencing')
        else:
            started.append('Mode: N/A')

        if (not is_functional_run) and is_rna:
            assembler = str(parameters.get('rnaAssemblySection', {}).get('assembler') or '').lower()
            if assembler == 'rnabloom':
                started.append('Transcriptome assembler: RNA-Bloom')
            elif assembler == 'trinity':
                started.append('Transcriptome assembler: Trinity')
            runs = start_section.get('rnaSequencingRunList') or []
            if runs:
                started.append('RNA sequencing accession(s):')
                started.extend([f"  - {_format_run_entry(run)}" for run in runs])
        elif (not is_functional_run) and is_dna:
            if assembly_section.get('canu'):
                started.append('Assembler: CANU')
            elif assembly_section.get('megahit'):
                started.append('Assembler: Megahit')
            runs = start_section.get('sequencingRunList') or []
            if runs:
                started.append('Sequencing accession(s):')
                started.extend([f"  - {_format_run_entry(run)}" for run in runs])
            if sequencing_cfg.get('depth') is not None:
                started.append(f"Sequencing coverage: {sequencing_cfg['depth']:.1f}x")

        if (not is_functional_run) and start_section.get('assemblyFileOnServer'):
            started.append(f"Assembly file: {start_section.get('assemblyFileOnServer')}")
        if (not is_functional_run) and start_section.get('assemblyAccession'):
            started.append(f"Assembly accession: {start_section.get('assemblyAccession')}")

        _append_lines(lines, 'Started data', started)

        if not is_functional_run:
            annotation_lines = [
                f"Remove duplicate sequences: {'100% Identity - Same length' if annotation_section.get('removeStrict') else ('100% Identity - lower length' if annotation_section.get('removeSoft') else 'All sequences are conserved')}",
                f"Minimal sequence length: {annotation_section.get('minLength', '0')}",
            ]
            _append_lines(lines, 'Annotation parameters', annotation_lines)

        brownaming_lines = [
            f"Skip Brownaming: {bool(brownaming_section.get('skip', False))}",
        ]
        if not brownaming_section.get('skip', False):
            excluded = brownaming_section.get('excludedTaxoList') or []
            if excluded:
                brownaming_lines.append('Excluded species:')
                for item in excluded:
                    sci = item.get('scientific_name') or item.get('scientificName') or 'Unknown'
                    tax = item.get('taxid') or item.get('taxID') or 'NA'
                    brownaming_lines.append(f"  - {sci} ({tax})")
            else:
                brownaming_lines.append('Excluded species: None')
            brownaming_lines.append(f"Taxonomic Expansion Limit: {brownaming_section.get('lastTaxid') or 'None'}")
            brownaming_lines.append(f"Exclude trEMBL: {bool(brownaming_section.get('excludeTrembl', False))}")

        _append_lines(lines, 'Brownaming parameters', brownaming_lines)

        if not is_functional_run:
            busco_lines = []
            if not is_rna:
                busco_lines.append(f"Evaluate the assembly completeness: {bool(busco_section.get('assembly', False))}")
            busco_lines.append(f"Evaluate the annotation completeness: {bool(busco_section.get('annotation', False))}")
            _append_lines(lines, 'Busco parameters', busco_lines)

        should_include_evidence = (not is_functional_run) and (not species.get('is_bacteria', False)) and (not is_rna) and (is_dna or bool(start_section.get('assembly')))
        if should_include_evidence:
            lines.append('Evidence information')
            lines.append('-' * 80)
            lines.append(_format_evidence_info(parameters))
            lines.append('')

        ordered_tools = ['brownaming'] if is_functional_run else ['blat', 'scipio', 'trinity', 'transdecoder', 'rnabloom', 'cd_hit', 'bowtie2', 'canu', 'megahit', 'augustus', 'prokka', 'busco', 'fastp', 'brownaming']
        display_names = {
            'blat': 'BLAT',
            'scipio': 'Scipio',
            'trinity': 'Trinity',
            'transdecoder': 'TransDecoder',
            'rnabloom': 'RNA-Bloom',
            'cd_hit': 'CD-HIT',
            'bowtie2': 'Bowtie 2',
            'canu': 'CANU',
            'megahit': 'Megahit',
            'augustus': 'Augustus',
            'prokka': 'Prokka',
            'busco': 'BUSCO',
            'fastp': 'fastp',
            'brownaming': 'Brownaming',
        }
        tool_lines = []
        for tool in ordered_tools:
            info = tool_versions.get(tool)
            if not info or not info.get('used_in_run'):
                continue
            tool_lines.append(f"- {display_names.get(tool, tool)}: {info['version']}")
        if tool_lines:
            lines.append('Tool versions')
            lines.append('-' * 80)
            lines.extend(tool_lines)
            lines.append('')

        report_path = os.path.join(output_run_path, 'parameters.txt')
        with open(report_path, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines) + '\n')
        return report_path
    except Exception as exc:
        print(f"[parameters_report] failed: {exc}")
        return None

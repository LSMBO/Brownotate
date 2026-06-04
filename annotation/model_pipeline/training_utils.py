import os
import re
import subprocess

from flask_app.commands import run_command


def run_etraining(run_id, species, genes_file, stdout_path, stderr_path, env, conda_bin_path=None, stop_codon_excluded=None):
    stop_flag = ''
    if stop_codon_excluded is True:
        stop_flag = ' --stopCodonExcludedFromCDS=true'

    command = f"etraining --species={species}{stop_flag} {genes_file}"
    stdout, stderr, returncode = run_command(
        command,
        run_id,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        env=env,
    )
    return {
        'command': command,
        'stdout': stdout,
        'stderr': stderr,
        'returncode': returncode,
    }


def count_locus(file_path):
    command = f"grep -c LOCUS {file_path}"
    output = subprocess.run(command, stdout=subprocess.PIPE, shell=True, check=False).stdout.decode().strip()
    try:
        return int(output)
    except ValueError:
        return 0


def count_stop_codon_messages(stderr_path):
    command = f"grep -c \"Variable stopCodonExcludedFromCDS set right\" {stderr_path}"
    output = subprocess.run(command, stdout=subprocess.PIPE, shell=True, check=False).stdout.decode().strip()
    try:
        return int(output)
    except ValueError:
        return 0


def collect_problematic_sequences(stderr_path, output_path):
    if not os.path.exists(stderr_path):
        with open(output_path, 'w') as output_file:
            output_file.write('')
        return

    pattern = re.compile(r'.*in sequence (\S+): .*')
    sequences = set()

    with open(stderr_path, 'r') as input_file:
        for line in input_file:
            match = pattern.match(line)
            if match:
                sequences.add(match.group(1))

    with open(output_path, 'w') as output_file:
        for seq in sorted(sequences):
            output_file.write(f"{seq}\n")


def extract_stop_probabilities(etrainout_file):
    with open(etrainout_file, 'r') as file:
        lines = file.readlines()

    tag = None
    taa = None
    tga = None

    for line in reversed(lines):
        if 'tag' in line:
            tag = line.strip().split()[-1].strip('()')
        elif 'taa' in line:
            taa = line.strip().split()[-1].strip('()')
        elif 'tga' in line:
            tga = line.strip().split()[-1].strip('()')

        if tag and taa and tga:
            break

    return tag, taa, tga


def update_stop_probabilities(cfg_parameter_file, tag, taa, tga):
    with open(cfg_parameter_file, 'r') as file:
        lines = file.readlines()

    with open(cfg_parameter_file, 'w') as file:
        for line in lines:
            if re.match(r'^/Constant/amberprob( ){19}.+', line):
                line = f"/Constant/amberprob                   {tag}   # Prob(stop codon = tag)\n"
            elif re.match(r'^/Constant/ochreprob( ){19}.+', line):
                line = f"/Constant/ochreprob                   {taa}   # Prob(stop codon = taa)\n"
            elif re.match(r'^/Constant/opalprob( ){20}.+', line):
                line = f"/Constant/opalprob                    {tga}   # Prob(stop codon = tga)\n"
            file.write(line)

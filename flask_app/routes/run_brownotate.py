import json, datetime, re
from flask import Blueprint, request, jsonify
from flask_app.database import find_one, update_one
from flask_app.commands import build_brownotate_command, run_command
from flask_app.extensions import socketio
import shutil, os
import time

run_brownotate_bp = Blueprint('run_brownotate_bp', __name__)

def run_failed(stdout, stderr, run_id, message):
	query = {'parameters.id': int(run_id)}
	update = {'$set': {'status': 'failed', 'stdout': stdout, 'stderr' : stderr}}
	update_one('runs', query, update)
	socketio.emit('runs_updated', {'run_id': run_id, 'status': 'failed', 'stdout': stdout, 'stderr': stderr})
	return jsonify({'status': 'error', 'message': message, 'stderr': stderr, 'stdout': stdout}), 500	

@run_brownotate_bp.route('/run_brownotate', methods=['POST'])
def run_brownotate():
	user = request.json.get('user')
	run_id = request.json.get('run_id')
	if not user or not run_id:
		return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

	results = find_one('runs', {'parameters.id': int(run_id)})

	if not results['data']:
		return jsonify({'status': 'error', 'message': 'Run not found in the MongoDB database'}), 400

	parameters = results['data']['parameters']
	current_datetime = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")
	query = {'parameters.id': parameters['id']}
	update = {
		'$set': {
			'parameters': parameters, 
			'status': 'running',
			'working_dir_id': current_datetime
		}
	}
		
	output_run_dir = f"output_runs/{current_datetime}"
	update_one('runs', query, update)
	socketio.emit('runs_updated', {'run_id': run_id, 'status': 'running'})
	 
	if user.startswith('workshop-cjfps'):
		fake_dir = f"output_runs/WORKSHOP_FAKE_RUN"
		shutil.copytree(fake_dir, output_run_dir)
		stdout = "Warning: This is a fake run for the workshop. Results data do not belong to your organism."
		stderr = ""
		if parameters['startSection']['assembly']:
			shutil.rmtree(f"{output_run_dir}/seq", ignore_errors=True)
			assembly_accession = parameters['startSection']['assemblyAccession']
			shutil.move(f"{output_run_dir}/genome/Androctonus_amoreuxi_Megahit.fasta", f"{output_run_dir}/genome/{assembly_accession[0]}_assembly.fasta")
		else:
			assembly_filename = parameters['species']['scientificName'].replace(" ", "_") + "_Megahit.fasta"
			shutil.move(f"{output_run_dir}/genome/Androctonus_amoreuxi_Megahit.fasta", f"{output_run_dir}/genome/{assembly_filename}")

		if parameters['buscoSection']['assembly'] == False:
			shutil.rmtree(f"{output_run_dir}/busco_genome", ignore_errors=True)
			os.remove(f"{output_run_dir}/Busco_genome.json")
		if parameters['buscoSection']['annotation'] == False:
			shutil.rmtree(f"{output_run_dir}/busco_annotation", ignore_errors=True)
			os.remove(f"{output_run_dir}/Busco_annotation.json")

		annotation_filename = parameters['species']['scientificName'].replace(" ", "_") + "_Brownotate.fasta"
		shutil.move(f"{output_run_dir}/Androctonus_amoreuxi_Brownotate.fasta", f"{output_run_dir}/{annotation_filename}")

		time.sleep(10)
  
	else:
		command = build_brownotate_command(parameters, current_datetime)
		stdout, stderr = run_command(command, run_id)
		print(f"Execution completed")
		print(f"stdout: {stdout}\n")
		print(f"stderr: {stderr}\n")
		if stderr:
			return run_failed(stdout, stderr, parameters['id'], "Command failed")

		
	if not output_run_dir:
		return run_failed(stdout, stderr, parameters['id'], 'Output directory not found')
		
	if 'Error : Number of genes and rawgenes is too low' in stdout:
		status = 'incomplete'
	else:
		status = 'completed'
  
	query = {'parameters.id': parameters['id']}
	update = {'$set': {'status': status, 'results_path': output_run_dir, 'stdout': stdout, 'stderr' : stderr}}
	update_one('runs', query, update)
	socketio.emit('runs_updated', {'run_id': parameters['id'], 'status': status})
	return jsonify({'status': 'success', 'message': 'Script executed and run updated successfully', 'stdout': stdout, 'stderr': stderr}), 200

from flask_app.database import insert_one, find_one, update_one, delete_one
import subprocess

def add_process(run_id, process, command):
    insert_one('processes', {
        'run_id': run_id,
        'process_id': process.pid,
        'command': command,
        'status': 'running'
    })
    return process

def get_process(run_id):
    process = find_one('processes', {'run_id': run_id})
    return process['data']

def update_process_status(run_id, status):
    update_one('processes', {'run_id': run_id}, {'$set': {'status': status}})

def remove_process(run_id):
    delete_one('processes', {'run_id': run_id})

def stop_process(run_id):
    process_data = get_process(run_id)
    if process_data:
        process_id = process_data['process_id']
        process = subprocess.Popen(f"kill {process_id}", shell=True)
        process.wait()
        remove_process(run_id)

def check_process(run_id):
    process_data = get_process(run_id)
    if not process_data:
        query = {'parameters.id': run_id}
        update = {'$set': {'status': 'failed'}}
        update_one('runs', query, update)
        
        
# running_processes = {}

# def add_process(run_id, process):
#     running_processes[run_id] = process

# def remove_process(run_id):
#     if run_id in running_processes:
#         del running_processes[run_id]

# def get_process(run_id):
#     return running_processes.get(run_id)

# def check_process(run_id):
#     process = running_processes.get(int(run_id))
#     if not process:
#         query = {'parameters.id': run_id}
#         update = {'$set': {'status': 'failed'}}
#         update_one('runs', query, update)
        

from flask_app.database import insert_one, find_one, find, update_one, delete_one
import subprocess
import psutil
import time

def add_process(run_id, pid, command, cpus):
    insert_one('processes', {
        'run_id': run_id,
        'process_id': pid,
        'command': command,
        'cpus': cpus,
        'status': 'running'
    })

def get_process(run_id):
    process = find_one('processes', {'run_id': run_id})
    return process['data']

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
    process_data = None
    for attempt in range(3):
        time.sleep(5)
        process_data = get_process(run_id)
        if process_data:
            break
        print(f"Run {run_id} not found in db.processes, attempt {attempt + 1}/3")
        
    
    if not process_data:
        print(f"Run {run_id} not found in db.processes after 3 attempts")
        query = {'parameters.id': run_id}
        update = {'$set': {'status': 'failed'}}
        update_one('runs', query, update)
        return False
    return True

def get_cpus_used():
    running_processes = find('processes', {'status': 'running'})
    total_cpus = sum(int(process['cpus']) for process in running_processes['data'])
    return total_cpus
        
def get_max_cpu_usage_by_process(process_name):
    worker_count = 0
    for process in psutil.process_iter(['name']):
        if process.info['name'] == process_name:
            worker_count += 1
    if process_name == 'gunicorn' and worker_count > 0:
        return worker_count - 1
    return worker_count
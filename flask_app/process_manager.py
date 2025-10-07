from flask_app.database import insert_one, find_one, find, update_one, delete_one, delete
import subprocess
import psutil
import signal
import os
import time

def add_process(run_id, pid, command, cpus):
    insert_one('processes', {
        'run_id': run_id,
        'process_id': pid,
        'command': command,
        'cpus': cpus,
        'status': 'running'
    })

def get_run_processes(run_id):
    process = find('processes', {'run_id': run_id})
    return process['data']

def remove_run_processes(run_id):
    delete('processes', {'run_id': run_id})

def remove_process(process_id):
    delete_one('processes', {'process_id': process_id})

def stop_run_processes(run_id):
    process_data = get_run_processes(run_id)
    if process_data:
        for pid in process_data:
            stop_process(pid['process_id'])
    remove_run_processes(run_id)
        
def stop_process(process_id):
    try:
        parent = psutil.Process(process_id)
    except psutil.NoSuchProcess:
        print(f"Parent process {process_id} not found")
        return

    children = parent.children(recursive=True)
    targets = [parent] + children

    for p in targets:
        try:
            p.send_signal(signal.SIGTERM)
        except psutil.NoSuchProcess:
            pass

    gone, alive = psutil.wait_procs(targets, timeout=10)

    for p in alive:
        try:
            print(f"Forcing kill of {p.pid}")
            p.kill()
        except psutil.NoSuchProcess:
            pass

    remove_process(process_id)
    

def check_process(run_id):
    process_data = None
    for attempt in range(3):
        process_data = get_run_processes(run_id)
        if process_data:
            break
        time.sleep(3)
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
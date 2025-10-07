import subprocess
import os
import shlex
import psutil
from utils import load_config
from flask_app.process_manager import add_process, remove_process

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
   
def run_command(command, wd, cpus=1, stdout_path=None, stderr_path=None, env=env, shell=False):
    process = None
    process_id = None
    try:
        print(f"\n{command}")
        if isinstance(command, str):
            command_args = shlex.split(command)
        else:
            command_args = command
        
        stdout_handle = open(stdout_path, 'w') if stdout_path else subprocess.PIPE
        stderr_handle = open(stderr_path, 'w') if stderr_path else subprocess.PIPE
        
        process = subprocess.Popen(
            command_args, 
            env=env, 
            stdout=stdout_handle, 
            stderr=stderr_handle, 
            text=True, 
            shell=shell,
            preexec_fn=os.setsid
        )
        process_id = process.pid
        add_process(wd, process_id, command, cpus)
        stdout, stderr = process.communicate()
        returncode = process.returncode

        if stdout_path:
            if stdout is None:
                stdout = ''
        if stderr_path:
            if stderr is None:
                stderr = ''
        return stdout, stderr, returncode
    finally:
        if 'stdout_handle' in locals() and stdout_handle not in (subprocess.PIPE, None):
            stdout_handle.close()
        if 'stderr_handle' in locals() and stderr_handle not in (subprocess.PIPE, None):
            stderr_handle.close()
        if process_id and psutil.pid_exists(process_id):
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass
        if process_id:
            remove_process(process_id)
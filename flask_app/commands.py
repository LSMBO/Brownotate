import subprocess
import os
import shlex
from utils import load_config
from flask_app.process_manager import add_process, remove_process

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
   
def run_command(command, wd, cpus=1, stdout_path=None, stderr_path=None, env=env):
    
    process = None
    try:
        print(f"\n{command}")
        if isinstance(command, str):
            command_args = shlex.split(command)
        else:
            command_args = command
        process = subprocess.Popen(command_args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
        process_id = process.pid
        add_process(wd, process_id, command, cpus)
        stdout, stderr = process.communicate()
        returncode = process.returncode

        if stdout_path:
            with open(stdout_path, 'w') as f:
                f.write(stdout)
        if stderr_path:
            with open(stderr_path, 'w') as f:
                f.write(stderr)

        remove_process(process_id)
        return stdout, stderr, returncode

    except subprocess.CalledProcessError as e:
        if process_id:
            remove_process(process_id)
        if stdout_path and e.stdout:
            with open(stdout_path, 'w') as f:
                f.write(e.stdout)
        if stderr_path and e.stderr:
            with open(stderr_path, 'w') as f:
                f.write(e.stderr)
        return e.stdout, e.stderr, e.returncode


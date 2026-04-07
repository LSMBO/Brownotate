import subprocess
import os
import shlex
import psutil
import docker
from .utils import load_config
from flask_app.process_manager import add_process, remove_process

config = load_config()
env = os.environ.copy()
env['PATH'] = os.path.join(config['BROWNOTATE_ENV_PATH'], 'bin') + os.pathsep + env['PATH']
   
def run_command(command, wd, cpus=1, stdout_path=None, stderr_path=None, env=env, shell=False, cwd=None):
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
            cwd=cwd,
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


def run_docker_command(image, command, wd, cpus=1, volumes=None, working_dir=None, env_vars=None, stdout_path=None, stderr_path=None, timeout=None):
    """
    Execute a command inside a Docker container with process tracking.
    
    Args:
        image: Docker image name (e.g., 'quay.io/biocontainers/canu:2.2--ha47f30e_0')
        command: Command to run inside the container (string or list)
        wd: Working directory ID for process tracking
        cpus: Number of CPUs to allocate
        volumes: Dict of host:container volume mappings (e.g., {'/host/path': '/container/path'})
        working_dir: Working directory inside the container
        env_vars: Dict of environment variables to set in the container
        stdout_path: Path to redirect stdout
        stderr_path: Path to redirect stderr
        timeout: Timeout in seconds for container operations (default: 2592000 for heavy operations)
    
    Returns:
        Tuple of (stdout, stderr, returncode)
    """
    container = None
    container_id = None
    try:
        print(f"\nRunning Docker command: {command}")
        print(f"Image: {image}")
        
        # Initialize Docker client with increased timeout for heavy operations
        # Default timeout is 60s which is too short for CANU and other heavy tools
        client_timeout = timeout if timeout is not None else 2592000  # 30 days default
        client = docker.from_env(timeout=client_timeout)
        
        # Prepare volumes
        volume_mounts = {}
        if volumes:
            for host_path, container_path in volumes.items():
                abs_host_path = os.path.abspath(host_path)
                volume_mounts[abs_host_path] = {
                    'bind': container_path,
                    'mode': 'rw'
                }
        
        # Prepare environment variables
        environment = env_vars if env_vars else {}
        
        # Convert command to proper format
        if isinstance(command, str):
            cmd = command
        else:
            cmd = ' '.join(command)
        
        # Get current user UID and GID (works across all systems)
        uid = os.getuid()
        gid = os.getgid()

        # Run container
        container = client.containers.run(
            image,
            command=cmd,
            volumes=volume_mounts,
            working_dir=working_dir,
            environment=environment,
            user=f'{uid}:{gid}',  # Use numeric UID:GID instead of username
            detach=True,
            remove=False, 
        )
        
        container_id = container.id
        
        # Get the actual process ID from Docker container
        # We use the container ID as a pseudo-PID for tracking
        process_id = hash(container_id) % (10 ** 8)  # Convert to a reasonable integer
        add_process(wd, process_id, f"docker:{cmd}", cpus)
        
        print(f"Docker container started with ID: {container_id}")
        print(f"Waiting for container to finish (this may take hours for heavy operations like CANU)...")
        
        # Stream logs in real-time to keep connection alive and provide progress updates
        # This prevents HTTP timeout issues with long-running containers like CANU
        logs_output = []
        try:
            for log_line in container.logs(stream=True, follow=True):
                line = log_line.decode('utf-8', errors='replace')
                logs_output.append(line)
                # Print every 100 lines to show progress without flooding
                if len(logs_output) % 100 == 0:
                    print(f"Container progress: {len(logs_output)} log lines received...")
            
            # Container has finished streaming, get final exit code
            container.reload()
            exit_code = container.attrs['State']['ExitCode']
            returncode = exit_code
            logs = ''.join(logs_output)
            print(f"Docker container finished with return code: {returncode}")
            print(f"Total output: {len(logs_output)} log lines, {len(logs)} bytes")
            
        except Exception as stream_error:
            print(f"Error during log streaming: {str(stream_error)}")
            print(f"Falling back to wait() method...")
            # Fallback to original wait method if streaming fails
            try:
                result = container.wait(timeout=client_timeout)
                returncode = result['StatusCode']
                logs = container.logs(stdout=True, stderr=True).decode('utf-8')
                print(f"Docker container finished with return code: {returncode} (fallback method)")
            except Exception as wait_error:
                print(f"Error in fallback wait: {str(wait_error)}")
                raise stream_error
        
        # Split logs into stdout and stderr if needed (Docker combines them)
        # For now, we'll put everything in stdout
        stdout = logs
        stderr = ''
        
        # Write to files if paths provided
        if stdout_path:
            with open(stdout_path, 'w') as f:
                f.write(stdout)
            stdout = ''
        
        if stderr_path:
            with open(stderr_path, 'w') as f:
                f.write(stderr)
            stderr = ''
        
        return stdout, stderr, returncode
        
    except docker.errors.ImageNotFound as e:
        error_msg = f"Docker image not found: {image}"
        print(error_msg)
        print(f"Full error: {str(e)}")
        return '', error_msg, 1
        
    except docker.errors.ContainerError as e:
        error_msg = f"Container error: {str(e)}"
        print(error_msg)
        return '', error_msg, e.exit_status
    
    except docker.errors.APIError as e:
        error_msg = f"Docker API error: {str(e)}"
        print(error_msg)
        print(f"Full error details: {e.explanation if hasattr(e, 'explanation') else 'No details'}")
        return '', error_msg, 1
        
    except Exception as e:
        error_msg = f"Docker command failed: {str(e)}"
        print(error_msg)
        return '', error_msg, 1
        
    finally:
        # Clean up container
        if container:
            try:
                container.remove(force=True)
            except Exception as e:
                print(f"Failed to remove container: {str(e)}")
        
        # Remove process from tracking
        if 'process_id' in locals() and process_id:
            remove_process(process_id)
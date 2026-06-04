"""
Server-side annotation orchestration engine.

Equivalent of AnnotationRun.js but running on the server.
Orchestrates the entire annotation pipeline from start to finish.
This is the single source of truth for step sequencing and execution.
"""

import threading
import time
from typing import Dict, List, Callable, Any
from flask_app.database import update_one, find_one
from flask_app.file_ops import move_wd_to_output_runs_folder
from flask_app.parameters_report import write_parameters_report, detect_brownotate_version
from bson.int64 import Int64
import os
import shutil

from rna.common import fasta_record_count


class AnnotationOrchestrator:
    """
    Main orchestrator that handles the complete annotation pipeline.
    Executes all steps in sequence based on parameters.
    """

    def __init__(self, run_id: int, parameters: Dict, cpus: int, sync_routes_callable: Callable):
        """
        Initialize orchestrator.
        
        Args:
            run_id: Unique run identifier
            parameters: Full parameters dict containing all section configs
            cpus: Number of CPUs to use
            sync_routes_callable: Reference to Flask test_client for calling sync routes
        """
        self.run_id = run_id
        self.parameters = parameters
        self.cpus = cpus
        self.sync_routes_callable = sync_routes_callable
        self.resume_data = {}
        self.timers = {}

    def _normalize_sequencing_files(self, sequencing_file_list):
        """Mirror the legacy client grouping for uploaded sequencing files."""
        if not sequencing_file_list:
            return []

        if isinstance(sequencing_file_list, str):
            sequencing_file_list = [sequencing_file_list]

        paired_files = {}
        result = []

        for raw_file_path in sequencing_file_list:
            file_path = raw_file_path[1:-1] if isinstance(raw_file_path, str) and raw_file_path.startswith('"') and raw_file_path.endswith('"') else raw_file_path
            file_name = str(file_path).split('/')[-1]
            base_name = (
                file_name
                .replace('.fastq.gz', '')
                .replace('.fastq', '')
                .replace('.fq.gz', '')
                .replace('.fq', '')
            )

            if base_name.endswith('1') or base_name.endswith('2'):
                accession = base_name[:-1]
                if accession not in paired_files:
                    paired_files[accession] = {'accession': accession, 'file_name': [], 'platform': None}
                paired_files[accession]['file_name'].append(f'"{file_path}"')
            else:
                result.append({'accession': base_name, 'file_name': f'"{file_path}"', 'platform': None})

        for entry in paired_files.values():
            if len(entry['file_name']) > 1:
                result.append(entry)
            else:
                result.append({'accession': entry['accession'], 'file_name': entry['file_name'], 'platform': None})

        return result

    def _is_rna_sequencing(self) -> bool:
        return bool(self.parameters.get('startSection', {}).get('rnaSequencing', False))
        
    def _update_progress(self, message: str):
        """Append a progress message in the same list format used by the legacy UI."""
        try:
            def _progress_key(label: str) -> str:
                return ''.join(ch if ch.isalnum() else '_' for ch in str(label)).strip('_').lower()

            for query in self._db_queries():
                run_result = find_one('runs', query)
                if run_result.get('status') != 'success' or not run_result.get('data'):
                    continue

                current_progress = run_result['data'].get('progress', [])
                if isinstance(current_progress, list):
                    progress_list = list(current_progress)
                elif current_progress:
                    progress_list = [current_progress]
                else:
                    progress_list = []

                if not progress_list or progress_list[-1] != message:
                    previous_label = progress_list[-1] if progress_list else None
                    progress_list.append(message)
                else:
                    previous_label = None

                now = int(time.time())
                updates = {'progress': progress_list}
                unset_fields = {}
                resume_data = run_result['data'].get('resumeData', {}) or {}
                finished_map = resume_data.get('progress_finished_at', {}) or {}
                key = _progress_key(message)
                updates[f'resumeData.progress_started_at.{key}'] = now
                unset_fields[f'resumeData.progress_finished_at.{key}'] = ''

                # Auto-close previous step timestamp when moving to the next one.
                if previous_label:
                    previous_key = _progress_key(previous_label)
                    if not finished_map.get(previous_key):
                        updates[f'resumeData.progress_finished_at.{previous_key}'] = now

                update_doc = {'$set': updates}
                if unset_fields:
                    update_doc['$unset'] = unset_fields

                result = update_one('runs', query, update_doc)
                if result['status'] == 'success':
                    return True
        except Exception as e:
            print(f"Error updating progress: {e}")
        return False
    
    def _update_resume_data(self, updates: Dict):
        """Update resumeData in database."""
        try:
            for query in self._db_queries():
                result = update_one('runs', query, {'$set': {f'resumeData.{k}': v for k, v in updates.items()}})
                if result['status'] == 'success':
                    return True
        except Exception as e:
            print(f"Error updating resumeData: {e}")
        return False
    
    def _update_timers(self, updates: Dict):
        """Update timers in database."""
        try:
            def _progress_key(label: str) -> str:
                return ''.join(ch if ch.isalnum() else '_' for ch in str(label)).strip('_').lower()

            def _timer_key(label: str) -> str:
                # Mongo field keys cannot contain dots, strip them from the human-readable label.
                return str(label).replace('.', '')

            for query in self._db_queries():
                set_updates = {f'timers.{_timer_key(k)}': v for k, v in updates.items()}
                now = int(time.time())
                for label in updates:
                    set_updates[f'resumeData.progress_finished_at.{_progress_key(label)}'] = now

                result = update_one('runs', query, {'$set': set_updates})
                if result['status'] == 'success':
                    return True
        except Exception as e:
            print(f"Error updating timers: {e}")
        return False
    
    def _mark_failed(self, error_message: str):
        """Mark run as failed."""
        try:
            for query in self._db_queries():
                result = update_one('runs', query, {'$set': {'status': 'failed', 'error': error_message}})
                if result['status'] == 'success':
                    return True
        except Exception as e:
            print(f"Error marking run as failed: {e}")
        return False
    
    def _mark_completed(self):
        """Mark run as completed."""
        try:
            brownotate_version = detect_brownotate_version(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
            self._update_resume_data({'brownotate_version': brownotate_version})

            run_dir = os.path.join('runs', str(self.run_id))
            annotation_dir = os.path.join(run_dir, 'annotation')

            if os.path.isdir(annotation_dir):
                # Remove temporary split/scipio directories to avoid duplicate storage after archiving.
                for item in os.listdir(annotation_dir):
                    item_path = os.path.join(annotation_dir, item)
                    if item.startswith('scipio_work_dir_') and os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    elif item.startswith('file_') and item.endswith('.fasta') and os.path.isfile(item_path):
                        try:
                            os.remove(item_path)
                        except OSError:
                            pass
                    elif item.endswith('_simplified.fasta') and os.path.isfile(item_path):
                        try:
                            os.remove(item_path)
                        except OSError:
                            pass

            output_run_path = None
            if os.path.isdir(run_dir):
                output_run_path = move_wd_to_output_runs_folder(str(self.run_id))

            run_data = None
            for query in self._db_queries():
                record = find_one('runs', query)
                if record.get('status') == 'success' and record.get('data'):
                    run_data = record['data']
                    break
            if output_run_path and run_data:
                write_parameters_report(run_data, output_run_path)

            for query in self._db_queries():
                updates = {'status': 'completed'}
                if output_run_path:
                    updates['results_path'] = output_run_path
                result = update_one('runs', query, {'$set': updates})
                if result['status'] == 'success':
                    return True
        except Exception as e:
            print(f"Error marking run as completed: {e}")
        return False
    
    def _db_queries(self):
        """Get list of queries to handle mixed BSON types for run_id."""
        return [
            {'parameters.id': Int64(self.run_id)},
            {'parameters.id': int(self.run_id)},
            {'parameters.id': str(self.run_id)},
        ]
    
    def _load_resume_data(self):
        """Load existing resume data from database."""
        try:
            for query in self._db_queries():
                run = find_one('runs', query)
                if run and run.get('status') == 'success' and run.get('data'):
                    self.resume_data = run['data'].get('resumeData', {}) or {}
                    return True
        except Exception as e:
            print(f"Error loading resume data: {e}")
        return False
    
    def _should_skip_step(self, step_name: str) -> bool:
        """Check if step was already completed (for resume)."""
        return step_name in self.resume_data
    
    def _call_sync_route(self, route_path: str, payload: Dict) -> Dict:
        """
        Call a synchronous route in a test client.
        
        Returns dict with keys: 'success', 'data', 'error', 'timer'
        """
        try:
            from flask import current_app
            with current_app.test_client() as client:
                response = client.post(route_path, json=payload)
                body = response.get_json(silent=True) or {}
                
                if response.status_code == 200 and body.get('status') == 'success':
                    return {
                        'success': True,
                        'data': body.get('data'),
                        'timer': body.get('timer'),
                        'message': body.get('message')
                    }
                else:
                    if isinstance(body, dict):
                        message = body.get('message') or f"HTTP {response.status_code}"
                        detail = body.get('detail')
                        returncode = body.get('returncode')
                        stderr = body.get('stderr')
                        stdout = body.get('stdout')

                        parts = [str(message)]
                        if returncode is not None:
                            parts.append(f"returncode={returncode}")
                        if detail:
                            parts.append(f"detail: {detail}")
                        elif stderr:
                            stderr_tail = '\n'.join(str(stderr).splitlines()[-20:])
                            if stderr_tail.strip():
                                parts.append(f"stderr: {stderr_tail}")
                        elif stdout:
                            stdout_tail = '\n'.join(str(stdout).splitlines()[-20:])
                            if stdout_tail.strip():
                                parts.append(f"stdout: {stdout_tail}")

                        error_msg = ' | '.join(parts)
                    else:
                        error_msg = str(response.data)
                    return {
                        'success': False,
                        'error': error_msg,
                        'status_code': response.status_code
                    }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _call_route_raw(self, route_path: str, payload: Dict) -> Dict:
        """Call a route and return the raw Flask response payload."""
        try:
            from flask import current_app
            with current_app.test_client() as client:
                response = client.post(route_path, json=payload)
                body = response.get_json(silent=True) or {}
                return {
                    'status_code': response.status_code,
                    'body': body,
                    'text': response.get_data(as_text=True),
                }
        except Exception as e:
            return {
                'status_code': 500,
                'body': {},
                'text': str(e),
            }

    def _wait_for_step_completion(self, step_name: str, poll_interval: int = 5) -> Dict:
        """Poll unified step state until the background step completes or fails."""
        from flask_app.step_status import get_step_status

        while True:
            status = get_step_status(self.run_id, step_name)
            current_status = status.get('status')

            if current_status == 'completed':
                return {
                    'success': True,
                    'result': status.get('result'),
                    'timer': status.get('timer'),
                    'detail': status.get('detail'),
                }

            if current_status == 'error':
                error_message = status.get('error') or status.get('detail') or f'{step_name} failed'
                return {
                    'success': False,
                    'error': error_message,
                    'detail': status.get('detail'),
                }

            time.sleep(poll_interval)

    def _remove_file_if_exists(self, path_value: str):
        if not path_value:
            return
        try:
            if os.path.isfile(path_value):
                os.remove(path_value)
        except OSError:
            pass

    def _remove_dir_if_exists(self, path_value: str):
        if not path_value:
            return
        if os.path.isdir(path_value):
            shutil.rmtree(path_value, ignore_errors=True)

    def _cleanup_rna_fastq_inputs(self, sequencing_file_list: List[Dict]):
        """Remove per-run RNA FASTQ files once assembly succeeds to save disk."""
        run_root = os.path.abspath(os.path.join('runs', str(self.run_id)))

        for entry in sequencing_file_list or []:
            files = entry.get('file_name') if isinstance(entry, dict) else entry
            if isinstance(files, list):
                file_candidates = files
            else:
                file_candidates = [files]

            for file_path in file_candidates:
                candidate = str(file_path or '').strip().strip('"')
                if not candidate:
                    continue
                candidate_abs = os.path.abspath(candidate)
                if candidate_abs.startswith(run_root + os.sep):
                    self._remove_file_if_exists(candidate_abs)

        self._remove_dir_if_exists(os.path.join('runs', str(self.run_id), 'seq'))

    def _prepare_rna_assembler_retry(self):
        """On resume after an assembler crash, clear stale RNA assembler outputs."""
        if self._should_skip_step('rna_assembler'):
            return
        if not self.resume_data:
            return

        self._remove_file_if_exists(self.resume_data.get('transcriptsFile'))
        self._remove_file_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'transcripts.fasta'))
        self._remove_file_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'rnabloom_transcripts.fasta'))
        self._remove_file_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'trinity_transcripts.fasta'))
        self._remove_dir_if_exists(self.resume_data.get('rnaAssemblerDir'))
        self._remove_dir_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'rnabloom'))
        self._remove_dir_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'trinity'))

    def _prepare_transdecoder_retry(self):
        """On resume after a TransDecoder crash, clear stale TransDecoder outputs."""
        if self._should_skip_step('transdecoder'):
            return
        if not self.resume_data:
            return

        self._remove_file_if_exists(self.resume_data.get('annotationFile'))
        self._remove_file_if_exists(self.resume_data.get('proteinsForBrownamingFile'))
        self._remove_file_if_exists(self.resume_data.get('proteinsCleanFile'))
        self._remove_file_if_exists(self.resume_data.get('proteinsRawFile'))
        self._remove_file_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'proteins.pep'))
        self._remove_file_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'proteins_for_brownaming.pep'))
        self._remove_file_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'transdecoder_clean.pep'))
        self._remove_file_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'transdecoder_raw.pep'))
        self._remove_dir_if_exists(self.resume_data.get('transdecoderDir'))
        self._remove_dir_if_exists(os.path.join('runs', str(self.run_id), 'rna', 'transdecoder'))
    
    # =========================================================================
    # STEP EXECUTION METHODS
    # =========================================================================
    
    def _run_download_sra(self):
        """Download sequencing files from SRA."""
        step_name = 'download_sra'
        if self._should_skip_step(step_name):
            resume_key = 'rnaSequencingFileList' if self._is_rna_sequencing() else 'sequencingFileList'
            return self.resume_data.get(resume_key)

        progress_label = 'Downloading RNA sequencing files from SRA ...' if self._is_rna_sequencing() else 'Downloading sequencing files from SRA ...'
        resume_key = 'rnaSequencingFileList' if self._is_rna_sequencing() else 'sequencingFileList'

        self._update_progress(progress_label)

        result = self._call_sync_route('/download_sra', {'parameters': self.parameters, 'run_id': self.run_id})
        if not result['success']:
            self._mark_failed(f"Error downloading SRA files: {result['error']}")
            return None

        seq_files = result['data']
        self._update_resume_data({resume_key: seq_files, 'download_sra': True})
        if result.get('timer'):
            self._update_timers({progress_label: result['timer']})

        return seq_files
    
    def _run_fastp(self, seq_files: List[str]) -> List[str]:
        """Run fastp on sequencing files."""
        step_name = 'fastp'
        if self._should_skip_step(step_name):
            return self.resume_data.get('sequencingFileListAfterFastp')
        
        # Skip if using CANU (has its own trimming) or if not requested
        if self.parameters.get('assemblySection', {}).get('canu') or \
           not self.parameters.get('assemblySection', {}).get('runFastp', True):
            return seq_files
        
        self._update_progress('Running fastp on sequencing files ...')
        
        result = self._call_sync_route('/run_fastp', {
            'parameters': self.parameters,
            'sequencing_file_list': seq_files
        })
        
        if not result['success']:
            self._mark_failed(f"Error running fastp: {result['error']}")
            return None
        
        processed_files = result['data']
        self._update_resume_data({'sequencingFileListAfterFastp': processed_files, 'fastp': True})
        if result.get('timer'):
            self._update_timers({'Running fastp on sequencing files ...': result['timer']})
        
        return processed_files
    
    def _run_remove_phix(self, seq_files: List[str]) -> List[str]:
        """Run bowtie2 to remove Phix contamination."""
        step_name = 'remove_phix'
        if self._should_skip_step(step_name):
            return self.resume_data.get('sequencingFileListAfterRemovePhix')
        
        # Skip if using CANU or if not requested
        if self.parameters.get('assemblySection', {}).get('canu') or \
           not self.parameters.get('assemblySection', {}).get('runBowtie2', True):
            return seq_files
        
        self._update_progress('Removing Phix from sequencing files ...')
        
        result = self._call_sync_route('/run_remove_phix', {
            'parameters': self.parameters,
            'sequencing_file_list': seq_files
        })
        
        if not result['success']:
            self._mark_failed(f"Error removing Phix: {result['error']}")
            return None
        
        processed_files = result['data']
        self._update_resume_data({'sequencingFileListAfterRemovePhix': processed_files, 'remove_phix': True})
        if result.get('timer'):
            self._update_timers({'Removing Phix from sequencing files ...': result['timer']})
        
        return processed_files
    
    def _run_assembler(self, seq_files: List[str]) -> str:
        """Run either CANU or MEGAHIT assembly."""
        # Check if already completed
        if self._should_skip_step('assembly'):
            return self.resume_data.get('assemblyFile')
        
        if self.parameters.get('assemblySection', {}).get('canu'):
            return self._run_canu(seq_files)
        else:
            return self._run_megahit(seq_files)

    def _run_rna_assembler(self, seq_files: List[str]) -> str:
        """Run the configured RNA assembler and return the transcriptome file."""
        step_name = 'rna_assembler'
        if self._should_skip_step(step_name):
            return self.resume_data.get('transcriptsFile')

        self._prepare_rna_assembler_retry()

        assembler = str(self.parameters.get('rnaAssemblySection', {}).get('assembler') or 'trinity').lower()
        if assembler == 'rnabloom':
            progress_label = 'Running RNA-Bloom transcriptome assembly ...'
            route_path = '/run_rnabloom'
        else:
            assembler = 'trinity'
            progress_label = 'Running Trinity transcriptome assembly ...'
            route_path = '/run_trinity'

        self._update_progress(progress_label)

        result = self._call_sync_route(route_path, {
            'parameters': self.parameters,
            'sequencing_file_list': seq_files,
            'run_id': self.run_id,
            'cpus': self.cpus
        })

        if not result['success']:
            self._update_resume_data({f'{assembler}_error': result['error']})
            self._mark_failed(f"Error running {assembler}: {result['error']}")
            return None

        assembly_data = result['data'] or {}
        transcripts_file = assembly_data.get('transcripts_file')
        if not transcripts_file:
            self._mark_failed(f"Error running {assembler}: transcriptome file was not produced")
            return None

        self._update_resume_data({
            'transcriptsFile': transcripts_file,
            'rnaAssemblerDir': assembly_data.get('assembly_dir'),
            'rnaAssembler': assembler,
            'rnaAssemblerLayout': assembly_data.get('layout'),
            'rna_assembler': True
        })

        # Once transcriptome is ready we can remove FASTQ inputs and heavy assembler work dirs.
        self._cleanup_rna_fastq_inputs(seq_files)
        self._remove_dir_if_exists(assembly_data.get('assembly_dir'))

        if result.get('timer'):
            self._update_timers({progress_label: result['timer']})

        return transcripts_file

    def _run_transdecoder(self, transcripts_file: str) -> str:
        """Run TransDecoder on the assembled transcriptome."""
        step_name = 'transdecoder'
        if self._should_skip_step(step_name):
            return self.resume_data.get('annotationFile') or self.resume_data.get('proteinsForBrownamingFile') or self.resume_data.get('proteinsRawFile')

        self._prepare_transdecoder_retry()

        self._update_progress('Running TransDecoder protein prediction ...')

        result = self._call_sync_route('/run_transdecoder', {
            'parameters': self.parameters,
            'transcripts_file': transcripts_file,
            'run_id': self.run_id
        })

        if not result['success']:
            self._update_resume_data({'transdecoder_error': result['error']})
            self._mark_failed(f"Error running TransDecoder: {result['error']}")
            return None

        payload = result.get('data') or {}
        proteins_raw = payload.get('proteins_raw_file')
        proteins_clean = payload.get('proteins_clean_file')
        proteins_for_brownaming = payload.get('proteins_for_brownaming_file') or proteins_clean or proteins_raw
        if not proteins_for_brownaming:
            self._mark_failed('Error running TransDecoder: protein file was not produced')
            return None

        if not self._ensure_non_empty_annotation_file(proteins_for_brownaming, 'TransDecoder normalization'):
            return None

        self._update_resume_data({
            'proteinsRawFile': proteins_raw,
            'proteinsCleanFile': proteins_clean,
            'proteinsForBrownamingFile': proteins_for_brownaming,
            'transdecoderDir': payload.get('transdecoder_dir'),
            'annotationFile': proteins_for_brownaming,
            'transdecoder': True
        })
        if result.get('timer'):
            self._update_timers({'Running TransDecoder protein prediction ...': result['timer']})

        return proteins_for_brownaming

    def _ensure_non_empty_annotation_file(self, annotation_file: str, stage_name: str) -> bool:
        """Fail early when a FASTA-producing stage leaves no protein records."""
        if fasta_record_count(annotation_file) > 0:
            return True

        error_msg = (
            f"RNA annotation file is empty after {stage_name}. "
            f"Check TransDecoder output and the post-processing filters before Brownaming. "
            f"File: {annotation_file}"
        )
        self._update_resume_data({'annotation_validation_error': error_msg, 'annotationFile': annotation_file})
        self._mark_failed(error_msg)
        return False
    
    def _run_canu(self, seq_files: List[str]) -> str:
        """Run CANU assembly."""
        self._update_progress('Running CANU assembly ...')

        launch = self._call_route_raw('/run_canu', {
            'parameters': self.parameters,
            'sequencing_file_list': seq_files
        })

        launch_body = launch.get('body') if isinstance(launch.get('body'), dict) else {}
        if launch.get('status_code') != 200 or launch_body.get('status') != 'started':
            launch_error = launch_body.get('message') or launch_body.get('error') or launch.get('text') or f"HTTP {launch.get('status_code')}"
            self._mark_failed(f"Error running CANU: {launch_error}")
            return None

        result = self._wait_for_step_completion('canu')
        if not result['success']:
            self._mark_failed(f"Error running CANU: {result['error']}")
            return None

        assembly_file = result['result']
        if not assembly_file:
            self._mark_failed('Error running CANU: assembly file was not produced')
            return None

        self._update_resume_data({'assemblyFile': assembly_file, 'canu': True, 'assembly': True})
        if result.get('timer'):
            self._update_timers({'Running CANU assembly ...': result['timer']})
        
        return assembly_file

    def _run_prokka(self, assembly_file: str) -> str:
        """Run Prokka for bacterial annotation."""
        step_name = 'prokka'
        if self._should_skip_step(step_name):
            return self.resume_data.get('annotationFile')

        self._update_progress('Running Prokka annotation ...')

        result = self._call_sync_route('/run_prokka', {
            'parameters': self.parameters,
            'assembly_file': assembly_file
        })

        if not result['success']:
            self._mark_failed(f"Error running Prokka: {result['error']}")
            return None

        annotation_file = result['data']
        self._update_resume_data({'annotationFile': annotation_file, 'prokka': True})
        if result.get('timer'):
            self._update_timers({'Running Prokka annotation ...': result['timer']})

        return annotation_file
    
    def _run_megahit(self, seq_files: List[str]) -> str:
        """Run MEGAHIT assembly."""
        self._update_progress('Running Megahit assembly ...')
        
        result = self._call_sync_route('/run_megahit', {
            'parameters': self.parameters,
            'sequencing_file_list': seq_files
        })
        
        if not result['success']:
            self._mark_failed(f"Error running MEGAHIT: {result['error']}")
            return None
        
        assembly_file = result['data']
        self._update_resume_data({'assemblyFile': assembly_file, 'megahit': True, 'assembly': True})
        if result.get('timer'):
            self._update_timers({'Running Megahit assembly ...': result['timer']})
        
        return assembly_file
    
    def _run_split_assembly(self, assembly_file: str) -> List[str]:
        """Split assembly file."""
        step_name = 'split_assembly'
        if self._should_skip_step(step_name):
            return self.resume_data.get('splitAssemblyFiles')
        
        self._update_progress('Splitting assembly for annotation ...')
        
        result = self._call_sync_route('/run_split_assembly', {
            'parameters': self.parameters,
            'assembly_file': assembly_file
        })
        
        if not result['success']:
            self._mark_failed(f"Error splitting assembly: {result['error']}")
            return None
        
        split_files = result['data']
        self._update_resume_data({'splitAssemblyFiles': split_files, 'split_assembly': True})
        if result.get('timer'):
            self._update_timers({'Splitting assembly for annotation ...': result['timer']})
        
        return split_files
    
    def _run_scipio(self, split_files: List[str], evidence_file: str, flex: bool = False) -> Dict:
        """Run Scipio."""
        step_name = 'scipio_flex' if flex else 'scipio'
        if self._should_skip_step(step_name):
            return self.resume_data.get('genesRaw')
        
        self._update_progress(f"Running {'flexible ' if flex else ''}Scipio ...")
        
        result = self._call_sync_route('/run_scipio', {
            'parameters': self.parameters,
            'split_assembly_files': split_files,
            'evidence_file': evidence_file,
            'flex': flex,
            'run_id': self.run_id
        })
        
        if not result['success']:
            self._mark_failed(f"Error running Scipio: {result['error']}")
            return None
        
        genes = result['data']
        resume_key = 'scipio_flex' if flex else 'scipio'
        self._update_resume_data({'genesRaw': genes, resume_key: True})
        if result.get('timer'):
            timer_key = f"Running {'flexible ' if flex else ''}Scipio ..."
            self._update_timers({timer_key: result['timer']})
        
        return genes
    
    def _run_model(self, genes: Dict) -> int:
        """Run gene prediction model. Returns number of genes."""
        step_name = 'model'
        if self._should_skip_step(step_name):
            return self.resume_data.get('numGenes')
        
        self._update_progress('Running gene prediction model ...')
        
        result = self._call_sync_route('/run_model', {
            'parameters': self.parameters,
            'genesraw': genes
        })
        
        if not result['success']:
            self._mark_failed(f"Error running model: {result['error']}")
            return None
        
        num_genes = result['data']
        self._update_resume_data({'numGenes': num_genes, 'model': True})
        if result.get('timer'):
            self._update_timers({'Running gene prediction model ...': result['timer']})
        
        return num_genes
    
    def _run_optimize_model(self, num_genes: int):
        """Optimize gene prediction model."""
        step_name = 'optimize_model'
        if self._should_skip_step(step_name):
            return True
        
        self._update_progress('Optimizing gene prediction model ...')
        
        result = self._call_sync_route('/run_optimize_model', {
            'parameters': self.parameters,
            'num_genes': num_genes,
            'run_id': self.run_id,
            'cpus': self.cpus
        })
        
        if not result['success']:
            self._mark_failed(f"Error optimizing model: {result['error']}")
            return False
        
        self._update_resume_data({'optimize_model': True})
        if result.get('timer'):
            self._update_timers({'Optimizing gene prediction model ...': result['timer']})
        
        return True
    
    def _run_augustus(self, split_files: List[str]) -> str:
        """Run Augustus annotation."""
        step_name = 'augustus'
        if self._should_skip_step(step_name):
            return self.resume_data.get('annotationFile')
        
        self._update_progress('Running Augustus annotation ...')
        
        result = self._call_sync_route('/run_augustus', {
            'parameters': self.parameters,
            'split_assembly_files': split_files
        })
        
        if not result['success']:
            self._mark_failed(f"Error running Augustus: {result['error']}")
            return None
        
        annotation_file = result['data']
        self._update_resume_data({'annotationFile': annotation_file, 'augustus': True})
        if result.get('timer'):
            self._update_timers({'Running Augustus annotation ...': result['timer']})
        
        return annotation_file
    
    def _run_remove_short_sequences(self, annotation_file: str) -> str:
        """Remove short sequences based on minLength filter."""
        step_name = 'remove_short_sequences'
        if self._should_skip_step(step_name):
            return self.resume_data.get('annotationFile')
        
        min_length = int(self.parameters.get('annotationSection', {}).get('minLength', 0))
        if min_length <= 0:
            return annotation_file
        
        progress_label = 'Removing short sequences from annotation according to the length filter ...'
        self._update_progress(progress_label)
        
        result = self._call_sync_route('/run_remove_short_sequences', {
            'parameters': self.parameters,
            'annotation_file': annotation_file
        })
        
        if not result['success']:
            self._mark_failed(f"Error removing short sequences: {result['error']}")
            return None
        
        processed_file = result['data']['annotation_file']
        if not self._ensure_non_empty_annotation_file(processed_file, 'remove_short_sequences'):
            return None
        self._update_resume_data({'annotationFile': processed_file, 'remove_short_sequences': True})
        if result.get('timer'):
            self._update_timers({progress_label: result['timer']})
        
        return processed_file
    
    def _run_remove_redundancy(self, annotation_file: str) -> str:
        """Remove redundancy from annotation."""
        step_name = 'remove_redundancy'
        if self._should_skip_step(step_name):
            return self.resume_data.get('annotationFile')
        
        # Check if any redundancy removal is requested
        remove_strict = self.parameters.get('annotationSection', {}).get('removeStrict', False)
        remove_soft = self.parameters.get('annotationSection', {}).get('removeSoft', False)
        
        if not (remove_strict or remove_soft):
            return annotation_file
        
        self._update_progress('Removing redundancy from annotation ...')
        
        result = self._call_sync_route('/run_remove_redundancy', {
            'parameters': self.parameters,
            'annotation_file': annotation_file
        })
        
        if not result['success']:
            self._mark_failed(f"Error removing redundancy: {result['error']}")
            return None
        
        processed_file = result['data']['annotation_file']
        if not self._ensure_non_empty_annotation_file(processed_file, 'remove_redundancy'):
            return None
        self._update_resume_data({'annotationFile': processed_file, 'remove_redundancy': True})
        if result.get('timer'):
            self._update_timers({'Removing redundancy from annotation ...': result['timer']})
        
        return processed_file
    
    def _run_brownaming(self, annotation_file: str) -> str:
        """Run Brownaming (protein name assignment)."""
        step_name = 'brownaming'
        if self._should_skip_step(step_name):
            return self.resume_data.get('annotationFile')
        
        if self.parameters.get('brownamingSection', {}).get('skip', False):
            return annotation_file

        if not self._ensure_non_empty_annotation_file(annotation_file, 'pre-Brownaming validation'):
            return None
        
        self._update_progress('Running Brownaming ...')
        
        result = self._call_sync_route('/run_brownaming', {
            'parameters': self.parameters,
            'annotation_file': annotation_file,
            'run_id': self.run_id,
            'cpus': self.cpus
        })

        # Brownaming can be interrupted by an external SIGTERM (e.g. service restart).
        # Try one resume attempt automatically before marking the run as failed.
        if not result['success'] and isinstance(result.get('error'), str) and 'code=-15' in result['error']:
            self._update_progress('Retrying Brownaming after interruption ...')
            result = self._call_sync_route('/run_brownaming', {
                'parameters': self.parameters,
                'annotation_file': annotation_file,
                'run_id': self.run_id,
                'cpus': self.cpus,
                'resume': True
            })
        
        if not result['success']:
            self._mark_failed(f"Error running Brownaming: {result['error']}")
            return None

        payload = result.get('data') if isinstance(result.get('data'), dict) else {}
        output_files = payload.get('output_files', {})
        fasta_rel = output_files.get('fasta')
        if not fasta_rel:
            self._mark_failed('Error running Brownaming: output FASTA file was not produced')
            return None

        annotation_file = f"runs/{self.run_id}/{fasta_rel}"
        
        self._update_resume_data({
            'annotationFile': annotation_file,
            'brownaming': True,
            'brownamingResults': output_files,
            'brownaming_dir': payload.get('brownaming_dir')
        })
        if result.get('timer'):
            self._update_timers({'Running Brownaming ...': result['timer']})
        
        return annotation_file
    
    def _run_busco(self, input_file: str, mode: str = 'genome') -> bool:
        """Run BUSCO."""
        step_name = f'busco_{mode}'
        if self._should_skip_step(step_name):
            return True
        
        progress_label = 'Running BUSCO on assembly ...' if mode == 'genome' else 'Running BUSCO on annotation ...'
        self._update_progress(progress_label)
        
        result = self._call_sync_route('/run_busco', {
            'parameters': self.parameters,
            'input_file': input_file,
            'mode': mode,
            'run_id': self.run_id
        })
        
        if not result['success']:
            self._mark_failed(f"Error running BUSCO ({mode}): {result['error']}")
            return False
        
        self._update_resume_data({step_name: True})
        if result.get('timer'):
            self._update_timers({progress_label: result['timer']})
        
        return True
    
    def _determine_pipeline_steps(self) -> List[tuple]:
        """
        Determine which steps to execute based on parameters.
        Returns list of (step_name, callable) tuples.
        """
        steps = []
        
        # 1. Sequencing phase
        if self.parameters.get('startSection', {}).get('sequencing'):
            steps.append(('download_sra', self._run_download_sra))
        
        # 2. Preprocessing phase
        steps.append(('fastp', self._run_fastp))
        steps.append(('remove_phix', self._run_remove_phix))
        
        # 3. Assembly phase
        steps.append(('assembly', self._run_assembler))
        
        # 4. Gene finding phase (DNA-based pipeline)
        if not self._is_rna_sequencing():
            steps.append(('split_assembly', self._run_split_assembly))
            steps.append(('scipio', self._run_scipio))
            steps.append(('model', self._run_model))
            steps.append(('optimize_model', self._run_optimize_model))
            steps.append(('augustus', self._run_augustus))
        else:
            steps.append(('rna_assembler', self._run_rna_assembler))
            steps.append(('transdecoder', self._run_transdecoder))
        
        # 5. Post-processing phase
        steps.append(('remove_short_sequences', self._run_remove_short_sequences))
        steps.append(('remove_redundancy', self._run_remove_redundancy))
        
        # 6. Annotation phase
        steps.append(('brownaming', self._run_brownaming))
        
        # 7. Quality assessment
        if self.parameters.get('buscoSection', {}).get('annotation'):
            steps.append(('busco_annotation', lambda af: self._run_busco(af, 'proteins')))
        
        if self.parameters.get('buscoSection', {}).get('assembly') and not self._is_rna_sequencing():
            steps.append(('busco_assembly', lambda af: self._run_busco(af, 'genome')))
        
        return steps
    
    def orchestrate(self):
        """
        Main orchestration method. Executes entire pipeline.
        Called in a background thread.
        """
        print(f"[ORCHESTRATOR] Starting annotation run {self.run_id}")
        
        # Load any existing resume data
        self._load_resume_data()

        # Persist Brownotate version early so it is visible in run parameters
        # before completion (running/failed states included).
        if not self.resume_data.get('brownotate_version'):
            try:
                brownotate_version = detect_brownotate_version(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
                self._update_resume_data({'brownotate_version': brownotate_version})
                self.resume_data['brownotate_version'] = brownotate_version
            except Exception as e:
                print(f"[ORCHESTRATOR] Failed to detect brownotate version at start: {e}")
        
        try:
            # Handle sequencing phase
            seq_files = None
            start_section = self.parameters.get('startSection', {})
            if self._is_rna_sequencing():
                has_rna_run_inputs = bool(
                    start_section.get('rnaSequencingRuns')
                    or start_section.get('rnaSequencingRunList')
                    or start_section.get('rnaSequencingSRA')
                )
                if self.resume_data.get('rnaSequencingFileList'):
                    seq_files = self.resume_data.get('rnaSequencingFileList')
                elif start_section.get('rnaSequencingFiles') and start_section.get('rnaSequencingFileListOnServer'):
                    seq_files = self._normalize_sequencing_files(start_section.get('rnaSequencingFileListOnServer'))
                    self._update_resume_data({'rnaSequencingFileList': seq_files})
                elif has_rna_run_inputs:
                    seq_files = self._run_download_sra()
                else:
                    self._mark_failed('RNA sequencing inputs are missing for orchestration')
                    return
                if seq_files is None:
                    return
            elif start_section.get('sequencing'):
                if self.resume_data.get('sequencingFileList'):
                    seq_files = self.resume_data.get('sequencingFileList')
                elif start_section.get('sequencingFiles') and start_section.get('sequencingFileListOnServer'):
                    seq_files = self._normalize_sequencing_files(start_section.get('sequencingFileListOnServer'))
                    self._update_resume_data({'sequencingFileList': seq_files})
                else:
                    seq_files = self._run_download_sra()
                if seq_files is None:
                    return
            
            # Handle preprocessing
            if start_section.get('sequencing'):
                seq_files = self._run_fastp(seq_files) if seq_files else seq_files
            if start_section.get('sequencing') and seq_files is None:
                return
            
            if start_section.get('sequencing'):
                seq_files = self._run_remove_phix(seq_files) if seq_files else seq_files
            if start_section.get('sequencing') and seq_files is None:
                return

            # Handle RNA sequencing annotation
            if self._is_rna_sequencing():
                transcripts_file = self._run_rna_assembler(seq_files)
                if transcripts_file is None:
                    return

                annotation_file = self._run_transdecoder(transcripts_file)
                if annotation_file is None:
                    return
                self._update_resume_data({'annotationFile': annotation_file})
            # Handle assembly
            elif start_section.get('sequencing'):
                assembly_file = self._run_assembler(seq_files) if seq_files else None
            else:
                assembly_file = self.resume_data.get('assemblyFile') or start_section.get('assemblyFileOnServer')
                if assembly_file:
                    self._update_resume_data({'assemblyFile': assembly_file})
                elif start_section.get('assembly'):
                    self._mark_failed('Assembly file on server is missing for orchestration')
                    return
                else:
                    assembly_file = None
            if not self._is_rna_sequencing() and assembly_file is None:
                return

            if self.parameters.get('buscoSection', {}).get('assembly') and not self._is_rna_sequencing() and not self.resume_data.get('buscoAssembly'):
                if not self._run_busco(assembly_file, 'genome'):
                    return
                self._update_resume_data({'buscoAssembly': True})
            
            # Handle annotation phases (only for DNA-based pipelines)
            if self._is_rna_sequencing():
                pass
            elif self.parameters.get('species', {}).get('is_bacteria'):
                annotation_file = self._run_prokka(assembly_file)
                if annotation_file is None:
                    return
            elif not self._is_rna_sequencing():
                # Split assembly and gene finding
                split_files = self._run_split_assembly(assembly_file)
                if split_files is None:
                    return
                
                # Get evidence file (for Scipio)
                evidence_file = (
                    self.parameters.get('annotationSection', {}).get('evidenceFileOnServer')
                    or self.parameters.get('annotationSection', {}).get('evidenceFile', '')
                )
                if not evidence_file:
                    self._mark_failed('Evidence file on server is missing for orchestration')
                    return
                
                # Run Scipio
                genes = self._run_scipio(split_files, evidence_file, flex=False)
                if genes is None:
                    return
                
                # Run model to predict genes
                num_genes = self._run_model(genes)
                if num_genes is None:
                    return
                
                # Flexible retry if < 200 genes
                if num_genes < 200:
                    self._update_progress(f'Less than 200 genes ({num_genes}), retrying with flexible Scipio ...')
                    genes = self._run_scipio(split_files, evidence_file, flex=True)
                    if genes is None:
                        return
                    
                    num_genes = self._run_model(genes)
                    if num_genes is None:
                        return
                    
                    # Still too few genes - stop
                    if num_genes < 200:
                        self._update_progress(f'Annotation stopped: insufficient genes predicted ({num_genes} < 200)')
                        self._mark_failed('Insufficient genes predicted after flexible mode')
                        return
                
                # Optimize model
                if not self._run_optimize_model(num_genes):
                    return
                
                # Run Augustus
                annotation_file = self._run_augustus(split_files)
                if annotation_file is None:
                    return
            
            # Post-processing
            annotation_file = self._run_remove_short_sequences(annotation_file)
            if annotation_file is None:
                return
            
            annotation_file = self._run_remove_redundancy(annotation_file)
            if annotation_file is None:
                return
            
            # Brownaming
            annotation_file = self._run_brownaming(annotation_file)
            if annotation_file is None:
                return
            
            # BUSCO
            if self.parameters.get('buscoSection', {}).get('annotation'):
                if not self._run_busco(annotation_file, 'proteins'):
                    return
            
            # Mark as completed
            self._mark_completed()
            self._update_progress('Annotation completed successfully!')
            
            print(f"[ORCHESTRATOR] Annotation run {self.run_id} completed successfully")
            
        except Exception as e:
            error_msg = f"Orchestration error: {str(e)}"
            print(f"[ORCHESTRATOR] {error_msg}")
            self._mark_failed(error_msg)

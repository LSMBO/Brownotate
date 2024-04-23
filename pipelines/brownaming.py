import os
import shutil

def run_brownaming(state, annotation):
    annotation.brownaming(annotation=os.path.abspath(state['annotation']), 
                                taxo=state['taxo'], 
                                output_name=os.path.basename(state['output_fasta_filepath']), 
                                directory_name="brownaming",
                                custom_db=state['brownaming']['custom_db'], 
                                exclude=state['brownaming']['exclude'], 
                                max_rank=state['brownaming']['max_rank'], 
                                max_taxo=state['brownaming']['max_taxo'],
                                cpus=state['args']['cpus'])
    
    shutil.copy(
        os.path.join("brownaming", os.path.basename(state['output_fasta_filepath'])), 
        state['output_fasta_filepath']
        )
    
    return state['output_fasta_filepath']
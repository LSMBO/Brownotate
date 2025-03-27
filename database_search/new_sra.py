import os, json

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '../config.json')
    with open(config_path, 'r') as config_file:
        return json.load(config_file)


def search_dna():
    config = load_config()
    Entrez.email = config['email']
    

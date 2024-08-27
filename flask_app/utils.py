import os, json

def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, '..', 'config.json')
    with open(config_path) as config_file:
        return json.load(config_file)
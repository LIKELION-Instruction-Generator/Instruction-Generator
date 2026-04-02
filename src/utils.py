import yaml
from dotenv import load_dotenv

def load_config(config_path):
    with open(config_path, "r", encoding = "utf-8") as f:
        config = yaml.safe_load(f)
        return config
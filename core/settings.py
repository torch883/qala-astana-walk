from pathlib import Path
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
CONFIG = yaml.safe_load((ROOT / 'config.yaml').read_text(encoding='utf-8'))
DATA = ROOT / 'data'

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
GRAMMAR_PATH = MODELS_DIR / "grammar" / "syntax.fcfg"
LEXICON_DIR = MODELS_DIR / "lexicon"
KB_DIR = DATA_DIR / "db"

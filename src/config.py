from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
GRAMMAR_PATH = DATA_DIR / "grammar" / "syntax.fcfg"
LEXICON_DIR = DATA_DIR / "lexicon"
KB_DIR = DATA_DIR / "KB"

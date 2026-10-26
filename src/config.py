"""Project paths and bounded runtime defaults shared by CLI and modules."""
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
GRAMMAR_PATH = MODELS_DIR / "grammar" / "syntax.fcfg"
LEXICON_DIR = MODELS_DIR / "lexicon"
KB_DIR = DATA_DIR / "db"

SQLITE_PATH = KB_DIR / "course_assistant_normalized.sqlite3"

RAW_DIR = DATA_DIR / "raw"
DEFAULT_SAMPLE_LIMIT = 100
MAX_SAMPLE_LIMIT = 10_000
GENERATION_MAX_DEPTH = 12
GENERATION_CANDIDATE_FACTOR = 20
SQLITE_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class RunConfig:
    input_path: Path = INPUT_DIR / "sentences.txt"
    output_dir: Path = OUTPUT_DIR
    database: Path = SQLITE_PATH
    evaluation_path: Path = INPUT_DIR / "test_cases.jsonl"
    sample_limit: int = DEFAULT_SAMPLE_LIMIT

    dialogue_path: Path = INPUT_DIR / "dialogues.txt"

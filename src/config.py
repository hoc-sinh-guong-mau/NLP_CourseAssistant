"""Validated process configuration: environment > .env > built-in defaults.

Load once at startup. Explicit RunConfig/CLI arguments override these defaults.
Relative environment paths are resolved against the chosen project root.
"""
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.common.errors import NLPError


class ConfigurationError(NLPError):
    stage = "configuration"
    code = "INVALID_CONFIGURATION"


def env_path(name, default, *, base):
    value = os.getenv(name)
    if value is not None and not value.strip():
        raise ConfigurationError(f"{name} cannot be empty")
    path = Path(default if value is None else value).expanduser()
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def env_number(name, default, *, minimum, maximum, integer=True):
    try:
        value = (int if integer else float)(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a valid number") from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


_SOURCE_ROOT = Path(__file__).resolve().parent.parent
_BUNDLED_ROOT = Path(sys.prefix) / "share" / "nlp-course-assistant"
_IS_SOURCE = (_SOURCE_ROOT / "models/grammar/syntax.fcfg").is_file()
_DEFAULT_ROOT = _SOURCE_ROOT if _IS_SOURCE else _BUNDLED_ROOT
# An explicit file is useful when starting outside the repository or in Docker.
_ENV_FILE = Path(os.environ.get("COURSE_ENV_FILE", Path.cwd() / ".env")).expanduser()
if "COURSE_ENV_FILE" in os.environ and not _ENV_FILE.is_file():
    raise ConfigurationError("COURSE_ENV_FILE must point to an existing file")
load_dotenv(_ENV_FILE, override=False, interpolate=False)

ROOT = env_path("COURSE_ROOT", _DEFAULT_ROOT, base=Path.cwd())
DATA_DIR = env_path("COURSE_DATA_DIR", ROOT / "data", base=ROOT)
MODELS_DIR = env_path("COURSE_MODELS_DIR", ROOT / "models", base=ROOT)
INPUT_DIR = env_path("COURSE_INPUT_DIR", ROOT / "input", base=ROOT)
# A wheel's bundled resources are read-only inputs, never a runtime workspace.
_RUNTIME_ROOT = ROOT if _IS_SOURCE else Path.cwd()
OUTPUT_DIR = env_path("COURSE_OUTPUT_DIR", _RUNTIME_ROOT / "output", base=_RUNTIME_ROOT)
KB_DIR = env_path("COURSE_DB_DIR", _RUNTIME_ROOT / "data/db", base=_RUNTIME_ROOT)
RAW_DIR = env_path("COURSE_RAW_DIR", DATA_DIR / "raw", base=ROOT)
GRAMMAR_PATH = env_path("COURSE_GRAMMAR_PATH", MODELS_DIR / "grammar/syntax.fcfg", base=ROOT)
LEXICON_DIR = env_path("COURSE_LEXICON_DIR", MODELS_DIR / "lexicon", base=ROOT)
SQLITE_PATH = env_path("COURSE_DATABASE", KB_DIR / "course_assistant_normalized.sqlite3", base=_RUNTIME_ROOT)

# Hard ceilings stay in code; deployment settings may lower working limits.
MAX_SAMPLE_LIMIT = 10_000
DEFAULT_SAMPLE_LIMIT = env_number("COURSE_SAMPLE_LIMIT", 100, minimum=1, maximum=MAX_SAMPLE_LIMIT)
GENERATION_MAX_DEPTH = env_number("COURSE_GENERATION_MAX_DEPTH", 12, minimum=1, maximum=50)
GENERATION_CANDIDATE_FACTOR = env_number("COURSE_GENERATION_CANDIDATE_FACTOR", 20, minimum=1, maximum=100)
SQLITE_TIMEOUT_SECONDS = env_number("COURSE_SQLITE_TIMEOUT", 5, minimum=0.1, maximum=300, integer=False)
MAX_VISIBLE_TURNS = env_number("COURSE_UI_MAX_TURNS", 50, minimum=1, maximum=1000)
LOG_LEVEL = os.getenv("COURSE_LOG_LEVEL", "INFO").upper()
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    raise ConfigurationError("COURSE_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")


@dataclass(frozen=True)
class RunConfig:
    input_path: Path = INPUT_DIR / "sentences.txt"
    output_dir: Path = OUTPUT_DIR
    database: Path = SQLITE_PATH
    evaluation_path: Path = INPUT_DIR / "test_cases.jsonl"
    sample_limit: int = DEFAULT_SAMPLE_LIMIT
    dialogue_path: Path = INPUT_DIR / "dialogues.txt"

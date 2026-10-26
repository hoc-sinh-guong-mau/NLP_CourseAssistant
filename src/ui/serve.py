"""Launch Streamlit without producing assignment artifacts."""
import os
import sys

from src.config import ROOT


def main():
    os.execv(sys.executable, [sys.executable, "-m", "streamlit", "run",
                             str(ROOT / "streamlit_app.py"), *sys.argv[1:]])


if __name__ == "__main__":
    main()

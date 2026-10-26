"""Container default: reproduce assignment outputs, then replace process with UI."""
import os
import sys

from src.application.runner import AssignmentRunner
from src.config import ROOT


def main():
    report = AssignmentRunner().run()
    if report['passed'] != report['total']:
        raise SystemExit(1)
    os.execv(sys.executable, [sys.executable, '-m', 'streamlit', 'run', str(ROOT / 'streamlit_app.py')])


if __name__ == '__main__':
    main()

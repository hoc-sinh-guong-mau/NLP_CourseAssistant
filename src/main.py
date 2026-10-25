import argparse
import json
from pathlib import Path
from src.config import ROOT, OUTPUT_DIR
from src.application.pipeline import CourseAssistant
from src.parsing.generator import generate_sentences
from src.artifacts.exporter import export_records, export_grammar


def main():
    parser = argparse.ArgumentParser(description="Classical NLP Course Assistant")
    commands = parser.add_subparsers(dest="command", required=True)
    batch = commands.add_parser("batch")
    batch.add_argument("--input", type=Path, default=ROOT / "input" / "sentences.txt")
    generate = commands.add_parser("generate")
    generate.add_argument("--limit", type=int, default=1000)
    commands.add_parser("chat")
    commands.add_parser("grammar", help="Validate and export output/grammar.txt")
    args = parser.parse_args()
    if args.command == "grammar":
        print(f"Grammar exported: {export_grammar()}")
        return
    if args.command == "generate":
        sentences = generate_sentences(args.limit)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "samples.txt").write_text("\n".join(sentences) + "\n", encoding="utf-8")
        print(f"Generated {len(sentences)} sentences.")
        return
    assistant = CourseAssistant()
    if args.command == "batch":
        texts = args.input.read_text(encoding="utf-8").splitlines()
        records = [assistant.process(text) for text in texts if text.strip()]
        export_records(records)
        print(f"Processed {len(records)} questions. Outputs: {OUTPUT_DIR}")
        return
    print("Course Assistant — dữ liệu minh họa. Gõ /exit để thoát.")
    while True:
        try:
            text = input("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if text.strip() == "/exit":
            break
        print(json.dumps(assistant.process(text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

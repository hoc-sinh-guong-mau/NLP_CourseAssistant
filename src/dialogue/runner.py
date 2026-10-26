"""Blank lines delimit independent dialogues; each nonblank line is one user turn."""
import json
import re
from pathlib import Path

from src.artifacts.exceptions import ArtifactError
from src.common.files import read_text, write_text
from .session import DialogueSession


def run_dialogues(assistant, input_path, output_path):
    input_path,output_path=Path(input_path),Path(output_path)
    if input_path.resolve()==output_path.resolve():
        raise ArtifactError('Dialogue input and output must be different files')
    text=read_text(input_path,ArtifactError,encoding='utf-8-sig').strip()
    groups=re.split(r'\n\s*\n',text) if text else []
    lines=[]
    for number,group in enumerate(groups,1):
        session=DialogueSession(assistant)
        lines.append(f'DIALOGUE {number:02}')
        for question in group.splitlines():
            if not question.strip():continue
            record=session.process(question.strip())
            lines.extend([
                f"TURN {record['turn']}",f"INPUT: {record['input']}",
                'CONTEXT_BEFORE: '+json.dumps(record['context_before'],ensure_ascii=False),
                'CONTEXT_USED: '+json.dumps(record['context_used'],ensure_ascii=False),
                'RAW_SEMANTIC: '+json.dumps(record.get('raw_semantic',record['semantic']),ensure_ascii=False),
                'RESOLVED_SEMANTIC: '+json.dumps(record['semantic'] if record['semantic'] and record['semantic']['predicate']!='CONTEXT_DEPENDENT' else None,ensure_ascii=False),
                'QUERY: '+json.dumps(record['query'],ensure_ascii=False),
                f"ANSWER: {record['answer']}",f"STATUS: {record['status']}",
                'CONTEXT_AFTER: '+json.dumps(record['context_after'],ensure_ascii=False),'',
            ])
    write_text(output_path,'\n'.join(lines),ArtifactError)
    return {'dialogues':len(groups)}

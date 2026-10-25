from src.preprocessing.preprocessor import normalize, tokenize

from src.parsing.parser import Parser
from src.semantic.interpreter import interpret
from src.semantic.intent_entity import extract
from src.retrieval.query_builder import build_query
from src.retrieval.knowledge_base import KnowledgeBase
from src.generation.answer import render


class CourseAssistant:
    def __init__(self):
        
        self.parser = Parser()
        self.kb = KnowledgeBase()

    def process(self, text):
        record = {
            "input": text, "tokens": tokenize(normalize(text)), "parse_tree": "()",
            "semantic": None, "intent_entity": None, "query": None,
            "result": [], "status": "parse_failed",
            "answer": "Tôi chưa hiểu cấu trúc câu. Ví dụ: Deadline bài tập lớn là khi nào?",
        }
        trees = self.parser.parse_all(record["tokens"])
        if not trees:
            return record
        frames = {str(interpret(tree).to_dict()): (tree, interpret(tree)) for tree in trees}
        if len(frames) > 1:
            record.update(
                status="ambiguous", answer="Câu hỏi có nhiều cách hiểu. Bạn vui lòng làm rõ.",
                alternatives=[frame.to_dict() for _, frame in frames.values()],
            )
            return record
        tree, frame = next(iter(frames.values()))
        record.update(parse_tree=tree.pformat(margin=10000),
                      semantic=frame.to_dict(), intent_entity=extract(frame))
        try:
            query = build_query(frame)
        except ValueError:
            record.update(status="unsupported_query",
                          answer="Tôi đã phân tích được câu hỏi nhưng chưa hỗ trợ truy vấn này.")
            return record
        result = self.kb.execute(query)
        status, answer = render(result)
        record.update(
            parse_tree=tree.pformat(margin=10000), semantic=frame.to_dict(),
            intent_entity=extract(frame), query=query, result=result,
            status=status, answer=answer,
        )
        return record

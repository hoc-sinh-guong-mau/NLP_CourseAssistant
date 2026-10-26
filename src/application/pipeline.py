"""Orchestrate NLP stages; implementations can be injected for tests/experiments."""
from src.preprocessing.preprocessor import normalize, tokenize
from src.parsing.parser import Parser
from src.semantic import SemanticInterpreter, UnsupportedSemanticError, InvalidSemanticError
from src.semantic.intent_entity import extract
from src.retrieval.query_builder import QueryBuilder, UnsupportedQueryError
from src.retrieval.knowledge_base import KnowledgeBase
from src.generation.answer import AnswerGenerator, UnsupportedAnswerError
from .messages import set_status


class CourseAssistant:
    def __init__(self, *, parser=None, semantic=None, kb=None, query_builder=None, answer_generator=None):
        self.parser = Parser() if parser is None else parser
        self.semantic = SemanticInterpreter() if semantic is None else semantic
        self.kb = KnowledgeBase() if kb is None else kb
        self.query_builder = QueryBuilder() if query_builder is None else query_builder
        self.answer_generator = AnswerGenerator() if answer_generator is None else answer_generator

    def _interpret_trees(self, trees):
        """Deduplicate equivalent frames, without selecting an arbitrary meaning."""
        frames = {}
        for tree in trees:
            frame = self.semantic.interpret(tree)
            frames[frame.canonical_key()] = (tree, frame)
        return list(frames.values())

    def process(self, text):
        normalized = normalize(text)
        record = {
            "input": text, "normalized": normalized, "tokens": tokenize(normalized),
            "parse_tree": "()", "semantic": None, "intent_entity": None,
            "query": None, "result": [],
        }
        trees = self.parser.parse_all(record["tokens"])
        record["parse_count"] = len(trees)
        if not trees:
            return set_status(record, "parse_failed")
        record["parse_tree"] = trees[0].pformat(margin=10000)
        try:
            interpretations = self._interpret_trees(trees)
        except UnsupportedSemanticError as exc:
            return set_status(record, "unsupported_semantic", detail=str(exc))
        except InvalidSemanticError as exc:
            return set_status(record, "invalid_semantic", detail=str(exc))
        if len(interpretations) > 1:
            return set_status(record, "ambiguous", alternatives=[f.to_dict() for _, f in interpretations])
        tree, frame = interpretations[0]
        record.update(parse_tree=tree.pformat(margin=10000),
                      semantic=frame.to_dict(), intent_entity=extract(frame))
        if frame.predicate == "CONTEXT_DEPENDENT":
            return set_status(record, "needs_context")
        try:
            record["query"] = self.query_builder.build(frame)
        except UnsupportedQueryError as exc:
            return set_status(record, "unsupported_query", detail=str(exc))
        record["result"] = self.kb.execute(record["query"])
        try:
            status, answer = self.answer_generator.render(frame, record["result"])
        except UnsupportedAnswerError as exc:
            return set_status(record, "unsupported_answer", detail=str(exc))
        record.update(status=status, answer=answer)
        return record

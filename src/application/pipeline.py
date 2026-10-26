"""Orchestrate NLP stages; implementations can be injected for tests/experiments."""
from src.common import NLPError, run_stage
from src.preprocessing import normalize, tokenize
from src.parsing import Parser, ParseError
from src.semantic import SemanticInterpreter, extract
from src.retrieval import QueryBuilder, KnowledgeBase
from src.generation import AnswerGenerator

from .messages import set_status


class CourseAssistant:
    def __init__(self, *, parser=None, semantic=None, kb=None, query_builder=None, answer_generator=None):
        self.parser = run_stage("grammar", Parser) if parser is None else parser
        self.semantic = run_stage("semantic", SemanticInterpreter) if semantic is None else semantic
        self.kb = run_stage("knowledge_base", KnowledgeBase) if kb is None else kb
        self.query_builder = run_stage("query", QueryBuilder) if query_builder is None else query_builder
        self.answer_generator = run_stage("generation", AnswerGenerator) if answer_generator is None else answer_generator

    def _interpret_trees(self, trees):
        """Deduplicate equivalent frames, without selecting an arbitrary meaning."""
        frames = {}
        for tree in trees:
            frame = run_stage("semantic", self.semantic.interpret, tree)
            frames[frame.canonical_key()] = (tree, frame)
        return list(frames.values())

    def process(self, text):
        record = {
            "input": text, "normalized": None, "tokens": [], "parse_tree": "()",
            "semantic": None, "intent_entity": None, "query": None, "result": [],
        }
        try:
            return self._process(text, record)
        except NLPError as exc:
            if exc.status is None:
                raise  # System/configuration errors keep traceback and original cause.
            return set_status(record, exc.status, detail=str(exc), error=exc.to_dict())

    def _process(self, text, record):
        normalized = run_stage("preprocessing", normalize, text)
        record.update(normalized=normalized, tokens=run_stage("preprocessing", tokenize, normalized))
        trees = run_stage("parsing", self.parser.parse_all, record["tokens"])
        record["parse_count"] = len(trees)
        if not trees:
            raise ParseError("No complete parse for the normalized input")
        record["parse_tree"] = trees[0].pformat(margin=10000)
        interpretations = self._interpret_trees(trees)
        if len(interpretations) > 1:
            return set_status(record, "ambiguous", alternatives=[f.to_dict() for _, f in interpretations])
        tree, frame = interpretations[0]
        record.update(parse_tree=tree.pformat(margin=10000),
                      semantic=frame.to_dict(),
                      intent_entity=run_stage("intent_entity", extract, frame))
        if frame.predicate == "CONTEXT_DEPENDENT":
            return set_status(record, "needs_context")
        record["query"] = run_stage("query", self.query_builder.build, frame)
        record["result"] = run_stage("knowledge_base", self.kb.execute, record["query"])
        status, answer = run_stage("generation", self.answer_generator.render, frame, record["result"])
        record.update(status=status, answer=answer)
        return record

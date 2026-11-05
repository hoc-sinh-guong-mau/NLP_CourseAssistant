"""Orchestrate NLP stages; implementations can be injected for tests/experiments."""
from src.common import NLPError, run_stage
from src.preprocessing import normalize, tokenize
from src.parsing import Parser, ParseError
from src.semantic import SemanticInterpreter, extract
from src.semantic import SemanticFrame
from src.semantic.rules import SEMANTIC_RULES
from src.config import LEXICON_DIR, QTYPE_MODEL_CONFIGURED, QTYPE_MODEL_PATH, ConfigurationError
from src.lexical import Lexicon
from src.retrieval import QueryBuilder
from src.retrieval.sqlite import SQLiteKnowledgeBase
from src.generation import AnswerGenerator
from src.statistical_processing.entity_extractor import EntityExtractor
from src.statistical_processing.intent_recognizer import QTypeRecognizer

from .messages import set_status


_QTYPE_TO_INTENT = {
    qtype: intent
    for intent, qtype in SEMANTIC_RULES
}


def _load_statistical_recognizer():
    if not QTYPE_MODEL_PATH.is_file():
        if QTYPE_MODEL_CONFIGURED:
            raise ConfigurationError(
                f"COURSE_QTYPE_MODEL does not point to a model file: {QTYPE_MODEL_PATH}"
            )
        return None

    return run_stage("statistical", QTypeRecognizer.load_model, QTYPE_MODEL_PATH)


class CourseAssistant:
    def __init__(
        self,
        *,
        parser=None,
        semantic=None,
        kb=None,
        query_builder=None,
        answer_generator=None,
        statistical_recognizer=None,
        entity_extractor=None,
    ):
        self.parser = run_stage("grammar", Parser) if parser is None else parser
        self.semantic = run_stage("semantic", SemanticInterpreter) if semantic is None else semantic
        self.kb = run_stage("knowledge_base", SQLiteKnowledgeBase) if kb is None else kb
        self.query_builder = run_stage("query", QueryBuilder) if query_builder is None else query_builder
        self.answer_generator = run_stage("generation", AnswerGenerator) if answer_generator is None else answer_generator
        self.statistical_recognizer = (
            _load_statistical_recognizer()
            if statistical_recognizer is None else statistical_recognizer
        )
        self.entity_extractor = entity_extractor
        if self.statistical_recognizer is not None and self.entity_extractor is None:
            lexicon = run_stage("statistical_entity", Lexicon.load, LEXICON_DIR)
            self.entity_extractor = EntityExtractor(lexicon)

    def _statistical_fallback(self, text: str, record: dict) -> SemanticFrame | None:
        if self.statistical_recognizer is None:
            return None

        qtype, confidence = run_stage(
            "statistical", self.statistical_recognizer.predict_with_confidence, text
        )
        intent = _QTYPE_TO_INTENT.get(qtype)
        record["statistical_prediction"] = {
            "intent": intent,
            "qtype": qtype,
            "confidence": confidence,
        }
        if intent is None:
            return None

        rule = SEMANTIC_RULES[(intent, qtype)]
        if self.entity_extractor is None:
            return None
        arguments = run_stage(
            "statistical_entity",
            self.entity_extractor.extract,
            text,
            rule.slots,
            rule.optional_slots,
        )
        if arguments is None:
            return None

        record["statistical_used"] = True
        return SemanticFrame(intent, arguments, qtype)

    def _interpret_trees(self, trees):
        """
        Interpret trees by sematic.interpret module.
        Deduplicate equivalent frames, without selecting an arbitrary meaning.

        :args:
        trees: ntlk tree
        :return:
        
        """
        frames = {}
        for tree in trees:
            frame = run_stage("semantic", self.semantic.interpret, tree)
            frames[frame.canonical_key()] = (tree, frame)
        return list(frames.values())

    def process(self, text, *, stop_after="answer", resolver=None):
        """
        Process input text to get the answer in record: dict

        :args:
        @text: input text

        :return:
        record (answer included)
        """
        
        if stop_after not in {"semantic", "intent_entity", "query", "answer"}:
            raise NLPError("Unknown pipeline stop stage", context={"stop_after": stop_after})
        
        record = {
            "input": text, "normalized": None, "tokens": [], "parse_tree": "()",
            "semantic": None, "intent_entity": None, "query": None, "result": [],
            "statistical_used": False, "statistical_prediction": None,
        }
        
        try:
            return self._process(text, record, stop_after, resolver)
        except NLPError as exc:
            if exc.status is None:
                raise  # System/configuration errors keep traceback and original cause.
            set_status(record, exc.status, detail=str(exc), error=exc.to_dict())
            if exc.stage == 'dialogue':
                record['answer'] = exc.message
                
            return record

    def _process(self, text: str, record: dict, stop_after: str, resolver):
        """
        |input text*| -> preprocessing |Text*|
                      -> parse |ParseTree*|
                      -> interpret |Semantic Frame (Predicate, args, qtype)*|
                      -> query ||

        """

        # Preprocessing
        normalized = run_stage("preprocessing", normalize, text)
        record.update(normalized=normalized, tokens=run_stage("preprocessing", tokenize, normalized))

        # Grammar parsing is authoritative; statistics only recovers a no-parse input.
        trees = run_stage("parsing", self.parser.parse_all, record["tokens"])
        record["parse_count"] = len(trees)
        if not trees:
            frame = self._statistical_fallback(normalized, record)
            if frame is None:
                raise ParseError("No complete parse for the normalized input")
            record["semantic"] = frame.to_dict()
        else:
            record["parse_tree"] = trees[0].pformat(margin=10000)

            # Interpret and deduplicate equivalent feature-grammar parses.
            interpretations = self._interpret_trees(trees)
            if len(interpretations) > 1:
                return set_status(record, "ambiguous", alternatives=[f.to_dict() for _, f in interpretations])
            tree, frame = interpretations[0]
            record.update(parse_tree=tree.pformat(margin=10000), semantic=frame.to_dict())
        
        if frame.predicate == "CONTEXT_DEPENDENT" and resolver is not None:
            record["raw_semantic"] = frame.to_dict()
            frame = run_stage("dialogue", resolver, frame)
            record["semantic"] = frame.to_dict()
            
        if stop_after == "semantic":
            return dict(record, status="semantic_ready", answer=None)

        
        record["intent_entity"] = run_stage("intent_entity", extract, frame)
        
        if stop_after == "intent_entity":
            return dict(record, status="intent_entity_ready", answer=None)
        
        if frame.predicate == "CONTEXT_DEPENDENT":
            return set_status(record, "needs_context")

        # Querry
        # build querry
        record["query"] = run_stage("query", self.query_builder.build, frame)
        
        if stop_after == "query":
            return dict(record, status="query_ready", answer=None)

        # execute querry
        record["result"] = run_stage("knowledge_base", self.kb.execute, record["query"])
        
        status, answer = run_stage("generation", self.answer_generator.render, frame, record["result"])
        
        record.update(status=status, answer=answer)
        return record

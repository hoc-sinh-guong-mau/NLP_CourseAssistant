"""Generate from a CFG projection, accepting only feature-valid sentences."""
from src.config import DEFAULT_SAMPLE_LIMIT, MAX_SAMPLE_LIMIT, GENERATION_MAX_DEPTH, GENERATION_CANDIDATE_FACTOR

from nltk.grammar import CFG, FeatureGrammar, Nonterminal, Production
from nltk.featstruct import TYPE
from nltk.parse.generate import generate

from .exceptions import GenerationError
from .parser import Parser
from .grammar_loader import load_grammar


def generate_sentences(limit=DEFAULT_SAMPLE_LIMIT) -> list[str]:
    """
    Args:
    @limit: how many sentences to generate
    Return:
    List of sentences: str
    
    Generate sentences by the prodecure:
    1. Load Grammar
    2. Project FCFG to CFG Grammar
    3. Generate Random Senteces by using ntlk.generate
    """

    
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_SAMPLE_LIMIT:
        raise GenerationError("limit must be between 1 and 10000")
    
    grammar: FeatureGrammar = load_grammar()
    productions: list[Production] = list(dict.fromkeys(
        Production(Nonterminal(p.lhs()[TYPE]), [
            symbol if isinstance(symbol, str) else Nonterminal(symbol[TYPE])
            for symbol in p.rhs()
        ]) for p in grammar.productions()
    ))
    projection: CFG = CFG(Nonterminal(grammar.start()[TYPE]), productions)
    parser: Parser = Parser(grammar)
    seen = set()
    sentences = []
    
    for tokens in generate(projection, depth=GENERATION_MAX_DEPTH, n=limit * GENERATION_CANDIDATE_FACTOR):
        sentence = " ".join(tokens)
        if sentence not in seen:
            seen.add(sentence)
            if parser.parse_all(tokens):
                sentences.append(sentence)
                if len(sentences) == limit:
                    break

    return sentences

"""Generate from a CFG projection, accepting only feature-valid sentences."""
from nltk.grammar import CFG, Nonterminal, Production
from nltk.featstruct import TYPE
from nltk.parse.generate import generate
from src.parsing.parser import Parser, load_grammar


def generate_sentences(limit=1000):
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    grammar = load_grammar()
    productions = list(dict.fromkeys(
        Production(Nonterminal(p.lhs()[TYPE]), [
            symbol if isinstance(symbol, str) else Nonterminal(symbol[TYPE])
            for symbol in p.rhs()
        ]) for p in grammar.productions()
    ))
    projection = CFG(Nonterminal(grammar.start()[TYPE]), productions)
    parser = Parser(grammar)
    seen = set()
    sentences = []
    for tokens in generate(projection, depth=12, n=limit * 20):
        sentence = " ".join(tokens)
        if sentence not in seen:
            seen.add(sentence)
            if parser.parse_all(tokens):
                sentences.append(sentence)
                if len(sentences) == limit:
                    break
    return sentences

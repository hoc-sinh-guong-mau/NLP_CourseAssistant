"""Domain exceptions with consistent stage/code metadata."""
from src.common import NLPError


class QueryError(NLPError):
    stage = 'query'
    code = 'QUERY_INVALID'


class UnsupportedQueryError(QueryError):
    stage = 'query'
    code = 'QUERY_UNSUPPORTED'
    status = 'unsupported_query'


class KnowledgeBaseError(NLPError):
    stage = 'knowledge_base'
    code = 'KB_INVALID'

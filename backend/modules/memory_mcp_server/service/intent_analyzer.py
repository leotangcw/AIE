"""Intent Analyzer for query understanding."""

from loguru import logger

from ..models.config import LLMConfig
from ..models.query import IntentResult, TypedQuery
from ..utils.llm import LLMClient, analyze_intent


class IntentAnalyzer:
    """
    Analyzes user queries to understand intent and generate optimized queries.

    Uses LLM to:
    1. Understand the true intent behind a query
    2. Determine what type of memory/context is needed
    3. Identify search scope
    4. Extract entities
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def analyze(
        self,
        query: TypedQuery,
        context: str | None = None,
    ) -> IntentResult:
        """
        Analyze a typed query and return structured intent.

        Args:
            query: The typed query with query text and metadata
            context: Optional session context for better understanding

        Returns:
            IntentResult with analyzed intent and suggested search parameters
        """
        try:
            # Use the LLM to analyze intent
            intent = analyze_intent(query.query_text, context, self.llm)

            # Override with explicit query parameters if provided
            if query.context_type != "all":
                intent.context_type = query.context_type

            logger.debug(
                f"Intent analysis: query='{query.query_text}' -> "
                f"intent='{intent.intent}', type={intent.context_type}, scope={intent.scope}"
            )

            return intent

        except Exception as e:
            logger.warning(f"Intent analysis failed: {e}")

            # Return default intent on failure
            return IntentResult(
                intent="General query",
                optimized_query=query.query_text,
                context_type=query.context_type,
                scope=self._infer_scope_from_query(query),
                entities=[],
                confidence=0.0,
            )

    def _infer_scope_from_query(self, query: TypedQuery) -> str:
        """Infer search scope from query metadata."""
        if query.session_id:
            return "session"
        elif query.user_id:
            return "user"
        elif query.agent_id:
            return "agent"
        else:
            return "global"

    def quick_analyze(self, query_text: str) -> IntentResult:
        """
        Quick intent analysis without full TypedQuery.

        Useful for simple queries where full metadata isn't needed.
        """
        from ..models.query import TypedQuery

        return self.analyze(TypedQuery(query_text=query_text))

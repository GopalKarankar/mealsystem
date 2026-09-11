from rest_framework.throttling import UserRateThrottle, SimpleRateThrottle


class LLMEndpointUserThrottle(UserRateThrottle):
    """Rate limit LLM-backed endpoints per authenticated user."""
    scope = "llm_endpoint_user"


class LLMEndpointIPThrottle(SimpleRateThrottle):
    """Rate limit LLM-backed endpoints per IP address."""
    scope = "llm_endpoint_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}

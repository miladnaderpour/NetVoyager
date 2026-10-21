
"""IPAM analysis models and entry points.

The legacy processor is imported only when requested, so observation
models do not depend on its migration status.
"""

from .models import SitePrefixAnalysisResult, SitePrefixAssociation

__all__ = [
    "SitePrefixAssociation",
    "SitePrefixAnalysisResult",
    "analyze_site_prefixes",
]


def __getattr__(name: str):
    if name == "analyze_site_prefixes":
        from .processing import analyze_site_prefixes

        return analyze_site_prefixes
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""ChoopScoop: a Playwright-powered site auditor and marketing tag detector."""

__version__ = "3.4.0"


def __getattr__(name):
    if name in ("audit_page", "format_page_llm", "format_site_llm"):
        from choopscoop import auditor
        return getattr(auditor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["audit_page", "format_page_llm", "format_site_llm", "__version__"]

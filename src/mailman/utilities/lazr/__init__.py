"""Lightweight LAZR compatibility package for Mailman.

This local package provides the small `lazr.config` subset Mailman needs on
platforms where the upstream dependency cannot be imported (for example native
Windows due to `grp`/`pwd`).
"""

__all__ = ["config"]


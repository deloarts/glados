"""
Glados // Infrastructure // Events

Event bus plumbing: codec (dataclass ↔ Redis Stream fields), the registry of
publishable event types, and the async consumer worker. Imported by main.py
and adapters, never by domain or application.
"""

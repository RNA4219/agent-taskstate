"""
Typed Reference Module

Provides canonical 4-segment typed_ref format for cross-repo entity references.

Format: <domain>:<entity_type>:<provider>:<entity_id>

Examples:
- agent-taskstate:task:local:task_01JXYZ...
- agent-taskstate:decision:local:dec_01JXYZ...
- memx:evidence:local:ev_01JXYZ...
- tracker:issue:github:owner/repo#123
- tracker:issue:jira:PROJ-123
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set, Tuple

# Known domains (can be extended)
KNOWN_DOMAINS: Set[str] = {"agent-taskstate", "memx", "tracker"}

# Default provider for local entities
DEFAULT_PROVIDER = "local"


@dataclass(frozen=True)
class TypedRef:
    """Immutable typed reference with 4 segments."""

    domain: str
    entity_type: str
    provider: str
    entity_id: str

    def __str__(self) -> str:
        return f"{self.domain}:{self.entity_type}:{self.provider}:{self.entity_id}"

    @property
    def is_local(self) -> bool:
        """Check if this is a local entity reference."""
        return self.provider == DEFAULT_PROVIDER


def format_ref(
    domain: str,
    entity_type: str,
    entity_id: str,
    provider: str = DEFAULT_PROVIDER,
) -> str:
    """
    Format a 4-segment typed_ref string.

    Args:
        domain: Domain namespace (agent-taskstate, memx, tracker)
        entity_type: Entity type (task, decision, evidence, etc.)
        entity_id: Entity identifier
        provider: Provider name (default: "local")

    Returns:
        Canonical typed_ref string

    Example:
        >>> format_ref("agent-taskstate", "task", "task_01JABC")
        'agent-taskstate:task:local:task_01JABC'
    """
    if not domain:
        raise ValueError("domain cannot be empty")
    if not entity_type:
        raise ValueError("entity_type cannot be empty")
    if not provider:
        raise ValueError("provider cannot be empty")
    if not entity_id:
        raise ValueError("entity_id cannot be empty")

    return f"{domain.lower()}:{entity_type.lower()}:{provider.lower()}:{entity_id}"


def parse_ref(ref: str) -> TypedRef:
    """
    Parse a typed_ref string into a TypedRef object.

    Accepts both 4-segment (canonical) and 3-segment (legacy) formats.
    Legacy format is automatically canonicalized with default provider.

    Args:
        ref: typed_ref string

    Returns:
        TypedRef object

    Raises:
        ValueError: If ref format is invalid

    Example:
        >>> parse_ref("agent-taskstate:task:local:task_01JABC")
        TypedRef(domain='agent-taskstate', entity_type='task', provider='local', entity_id='task_01JABC')
        >>> parse_ref("agent-taskstate:task:task_01JABC")  # legacy 3-segment
        TypedRef(domain='agent-taskstate', entity_type='task', provider='local', entity_id='task_01JABC')
    """
    parts = ref.split(":")

    if len(parts) == 4:
        domain, entity_type, provider, entity_id = parts
    elif len(parts) == 3:
        domain, entity_type, entity_id = parts
        provider = DEFAULT_PROVIDER
    else:
        raise ValueError(
            f"Invalid typed_ref format: {ref!r}. "
            f"Expected 3 or 4 segments separated by ':'."
        )

    if not domain:
        raise ValueError("domain cannot be empty")
    if not entity_type:
        raise ValueError("entity_type cannot be empty")
    if not provider:
        raise ValueError("provider cannot be empty")
    if not entity_id:
        raise ValueError("entity_id cannot be empty")

    return TypedRef(
        domain=domain.lower(),
        entity_type=entity_type.lower(),
        provider=provider.lower(),
        entity_id=entity_id,
    )


def validate_ref(ref: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a typed_ref string format.

    Args:
        ref: typed_ref string to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_ref("agent-taskstate:task:local:task_01JABC")
        (True, None)
        >>> validate_ref("invalid")
        (False, "Invalid typed_ref format...")
    """
    try:
        parsed = parse_ref(ref)
        if not is_known_domain(parsed.domain):
            return False, f"Unknown typed_ref domain: {parsed.domain}"
        return True, None
    except ValueError as e:
        return False, str(e)


def is_valid_ref(ref: str) -> bool:
    """
    Check if a typed_ref string has valid format.

    Args:
        ref: typed_ref string to check

    Returns:
        True if valid, False otherwise
    """
    return validate_ref(ref)[0]


def canonicalize_ref(ref: str) -> str:
    """
    Canonicalize a typed_ref string to 4-segment format.

    Accepts both 3-segment (legacy) and 4-segment formats.
    Always returns 4-segment canonical format.

    Args:
        ref: typed_ref string

    Returns:
        Canonical 4-segment typed_ref string

    Raises:
        ValueError: If ref format is invalid

    Example:
        >>> canonicalize_ref("agent-taskstate:task:task_01JABC")
        'agent-taskstate:task:local:task_01JABC'
        >>> canonicalize_ref("agent-taskstate:task:local:task_01JABC")
        'agent-taskstate:task:local:task_01JABC'
    """
    parsed = parse_ref(ref)
    if not is_known_domain(parsed.domain):
        raise ValueError(f"Unknown typed_ref domain: {parsed.domain}")
    return str(parsed)


def is_known_domain(domain: str) -> bool:
    """
    Check if a domain is in the known domains set.

    Args:
        domain: Domain name to check

    Returns:
        True if known domain, False otherwise
    """
    return domain.lower() in KNOWN_DOMAINS


# Convenience functions for common domains

def agent_taskstate_ref(entity_type: str, entity_id: str, provider: str = DEFAULT_PROVIDER) -> str:
    """Create an agent-taskstate typed_ref."""
    return format_ref("agent-taskstate", entity_type, entity_id, provider)


def memx_ref(entity_type: str, entity_id: str, provider: str = DEFAULT_PROVIDER) -> str:
    """Create a memx typed_ref."""
    return format_ref("memx", entity_type, entity_id, provider)


def tracker_ref(entity_type: str, entity_id: str, provider: str) -> str:
    """Create a tracker typed_ref (provider required)."""
    return format_ref("tracker", entity_type, entity_id, provider)

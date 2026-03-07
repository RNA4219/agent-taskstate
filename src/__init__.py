"""agent-taskstate source package."""

from .typed_ref import (
    TypedRef,
    canonicalize_ref,
    format_ref,
    is_known_domain,
    is_valid_ref,
    memx_ref,
    parse_ref,
    tracker_ref,
    validate_ref,
    workx_ref,
)

from .state_transition import (
    StateTransition,
    StateTransitionService,
    InvalidTransitionError,
    TerminalStateError,
    MissingReasonError,
    can_transition,
    is_terminal,
    requires_reason,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
)

from .context_bundle import (
    ContextBundle,
    BundleSource,
    ContextBundleService,
    REBUILD_LEVELS,
    PURPOSE_TYPES,
    SOURCE_KINDS,
)

from .resolver import (
    ContextRebuildResolver,
    ResolveStatus,
    ResolvedRef,
    ResolveReport,
    SummaryPayload,
    RawPayload,
    ResolverDiagnostics,
    WorkxLocalResolver,
    RAW_DESCENT_CONDITIONS,
)

from .tracker_bridge import (
    TrackerBridgeService,
    TrackerConnection,
    IssueCache,
    EntityLink,
    SyncEvent,
    IssueSnapshot,
    SyncSuggestion,
    SyncDirection,
    SyncStatus,
    LinkRole,
    MockTrackerAdapter,
    create_tracker_tables,
)

__all__ = [
    # typed_ref
    "TypedRef",
    "canonicalize_ref",
    "format_ref",
    "is_known_domain",
    "is_valid_ref",
    "memx_ref",
    "parse_ref",
    "tracker_ref",
    "validate_ref",
    "workx_ref",
    # state_transition
    "StateTransition",
    "StateTransitionService",
    "InvalidTransitionError",
    "TerminalStateError",
    "MissingReasonError",
    "can_transition",
    "is_terminal",
    "requires_reason",
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATES",
    # context_bundle
    "ContextBundle",
    "BundleSource",
    "ContextBundleService",
    "REBUILD_LEVELS",
    "PURPOSE_TYPES",
    "SOURCE_KINDS",
    # resolver
    "ContextRebuildResolver",
    "ResolveStatus",
    "ResolvedRef",
    "ResolveReport",
    "SummaryPayload",
    "RawPayload",
    "ResolverDiagnostics",
    "WorkxLocalResolver",
    "RAW_DESCENT_CONDITIONS",
    # tracker_bridge
    "TrackerBridgeService",
    "TrackerConnection",
    "IssueCache",
    "EntityLink",
    "SyncEvent",
    "IssueSnapshot",
    "SyncSuggestion",
    "SyncDirection",
    "SyncStatus",
    "LinkRole",
    "MockTrackerAdapter",
    "create_tracker_tables",
]
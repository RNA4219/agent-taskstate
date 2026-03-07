"""
Tests for typed_ref module.

Covers:
- 4-segment canonical format
- 3-segment legacy format compatibility
- Validation rules
- Canonicalization
"""

import pytest

from src.typed_ref import (
    TypedRef,
    canonicalize_ref,
    format_ref,
    is_known_domain,
    is_valid_ref,
    memx_ref,
    parse_ref,
    tracker_ref,
    validate_ref,
    agent_taskstate_ref,
)


class TestFormatRef:
    """Test format_ref function."""

    def test_format_with_default_provider(self):
        """Format with default provider 'local'."""
        result = format_ref("agent-taskstate", "task", "task_01JABC")
        assert result == "agent-taskstate:task:local:task_01JABC"

    def test_format_with_explicit_provider(self):
        """Format with explicit provider."""
        result = format_ref("tracker", "issue", "PROJ-123", "jira")
        assert result == "tracker:issue:jira:PROJ-123"

    def test_format_github_issue(self):
        """Format GitHub issue reference."""
        result = format_ref("tracker", "issue", "owner/repo#123", "github")
        assert result == "tracker:issue:github:owner/repo#123"


class TestParseRef:
    """Test parse_ref function."""

    def test_parse_4_segment(self):
        """Parse canonical 4-segment format."""
        ref = parse_ref("agent-taskstate:task:local:task_01JABC")
        assert ref.domain == "agent-taskstate"
        assert ref.entity_type == "task"
        assert ref.provider == "local"
        assert ref.entity_id == "task_01JABC"

    def test_parse_3_segment_legacy(self):
        """Parse legacy 3-segment format (auto-canonicalize)."""
        ref = parse_ref("agent-taskstate:task:task_01JABC")
        assert ref.domain == "agent-taskstate"
        assert ref.entity_type == "task"
        assert ref.provider == "local"  # Default provider
        assert ref.entity_id == "task_01JABC"

    def test_parse_uppercase_domain_normalized(self):
        """Uppercase domain is normalized to lowercase."""
        ref = parse_ref("AGENT-TASKSTATE:TASK:LOCAL:task_01JABC")
        assert ref.domain == "agent-taskstate"
        assert ref.entity_type == "task"
        assert ref.provider == "local"

    def test_parse_entity_id_preserves_case(self):
        """Entity ID preserves original case."""
        ref = parse_ref("tracker:issue:jira:PROJ-123")
        assert ref.entity_id == "PROJ-123"

    def test_parse_invalid_too_few_segments(self):
        """Invalid ref with too few segments raises ValueError."""
        with pytest.raises(ValueError, match="Invalid typed_ref format"):
            parse_ref("agent-taskstate:task")

    def test_parse_invalid_too_many_segments(self):
        """Invalid ref with too many segments raises ValueError."""
        with pytest.raises(ValueError, match="Invalid typed_ref format"):
            parse_ref("a:b:c:d:e")

    def test_parse_empty_domain(self):
        """Empty domain raises ValueError."""
        with pytest.raises(ValueError, match="domain cannot be empty"):
            parse_ref(":task:local:id")

    def test_parse_empty_entity_type(self):
        """Empty entity_type raises ValueError."""
        with pytest.raises(ValueError, match="entity_type cannot be empty"):
            parse_ref("agent-taskstate::local:id")

    def test_parse_empty_provider(self):
        """Empty provider raises ValueError."""
        with pytest.raises(ValueError, match="provider cannot be empty"):
            parse_ref("agent-taskstate:task::id")

    def test_parse_empty_entity_id(self):
        """Empty entity_id raises ValueError."""
        with pytest.raises(ValueError, match="entity_id cannot be empty"):
            parse_ref("agent-taskstate:task:local:")


class TestTypedRef:
    """Test TypedRef dataclass."""

    def test_str_representation(self):
        """String representation is canonical format."""
        ref = TypedRef("agent-taskstate", "task", "local", "task_01JABC")
        assert str(ref) == "agent-taskstate:task:local:task_01JABC"

    def test_is_local_true(self):
        """is_local is True for local provider."""
        ref = TypedRef("agent-taskstate", "task", "local", "task_01JABC")
        assert ref.is_local is True

    def test_is_local_false(self):
        """is_local is False for non-local provider."""
        ref = TypedRef("tracker", "issue", "jira", "PROJ-123")
        assert ref.is_local is False

    def test_frozen(self):
        """TypedRef is immutable."""
        ref = TypedRef("agent-taskstate", "task", "local", "task_01JABC")
        with pytest.raises(AttributeError):
            ref.domain = "memx"


class TestValidateRef:
    """Test validate_ref and is_valid_ref functions."""

    def test_validate_valid_4_segment(self):
        """Valid 4-segment ref passes validation."""
        is_valid, error = validate_ref("agent-taskstate:task:local:task_01JABC")
        assert is_valid is True
        assert error is None

    def test_validate_valid_3_segment(self):
        """Valid 3-segment legacy ref passes validation."""
        is_valid, error = validate_ref("agent-taskstate:task:task_01JABC")
        assert is_valid is True
        assert error is None

    def test_validate_invalid_format(self):
        """Invalid format fails validation."""
        is_valid, error = validate_ref("invalid")
        assert is_valid is False
        assert "Invalid typed_ref format" in error

    def test_is_valid_true(self):
        """is_valid_ref returns True for valid ref."""
        assert is_valid_ref("agent-taskstate:task:local:task_01JABC") is True

    def test_is_valid_false(self):
        """is_valid_ref returns False for invalid ref."""
        assert is_valid_ref("invalid") is False


class TestCanonicalizeRef:
    """Test canonicalize_ref function."""

    def test_canonicalize_4_segment_unchanged(self):
        """4-segment ref is unchanged."""
        result = canonicalize_ref("agent-taskstate:task:local:task_01JABC")
        assert result == "agent-taskstate:task:local:task_01JABC"

    def test_canonicalize_3_segment_adds_provider(self):
        """3-segment ref is canonicalized with default provider."""
        result = canonicalize_ref("agent-taskstate:task:task_01JABC")
        assert result == "agent-taskstate:task:local:task_01JABC"

    def test_canonicalize_memx_evidence(self):
        """Memx evidence ref is canonicalized."""
        result = canonicalize_ref("memx:evidence:ev_01JABC")
        assert result == "memx:evidence:local:ev_01JABC"


class TestConvenienceFunctions:
    """Test convenience functions for common domains."""

    def test_agent_taskstate_ref(self):
        """agent_taskstate_ref creates correct reference."""
        result = agent_taskstate_ref("task", "task_01JABC")
        assert result == "agent-taskstate:task:local:task_01JABC"

    def test_agent_taskstate_ref_with_provider(self):
        """agent_taskstate_ref with explicit provider."""
        result = agent_taskstate_ref("task", "task_01JABC", "remote")
        assert result == "agent-taskstate:task:remote:task_01JABC"

    def test_memx_ref(self):
        """memx_ref creates correct reference."""
        result = memx_ref("evidence", "ev_01JABC")
        assert result == "memx:evidence:local:ev_01JABC"

    def test_tracker_ref(self):
        """tracker_ref creates correct reference."""
        result = tracker_ref("issue", "PROJ-123", "jira")
        assert result == "tracker:issue:jira:PROJ-123"


class TestIsKnownDomain:
    """Test is_known_domain function."""

    def test_known_domain_agent_taskstate(self):
        """agent-taskstate is a known domain."""
        assert is_known_domain("agent-taskstate") is True

    def test_known_domain_memx(self):
        """memx is a known domain."""
        assert is_known_domain("memx") is True

    def test_known_domain_tracker(self):
        """tracker is a known domain."""
        assert is_known_domain("tracker") is True

    def test_unknown_domain(self):
        """unknown is not a known domain."""
        assert is_known_domain("unknown") is False

    def test_case_insensitive(self):
        """Domain check is case insensitive."""
        assert is_known_domain("AGENT-TASKSTATE") is True
        assert is_known_domain("MemX") is True


class TestIntegrationScenarios:
    """Integration test scenarios from P1 requirements."""

    def test_agent_taskstate_task_ref(self):
        """agent-taskstate task reference example."""
        ref = agent_taskstate_ref("task", "task_01JXYZ")
        assert ref == "agent-taskstate:task:local:task_01JXYZ"

    def test_agent_taskstate_decision_ref(self):
        """agent-taskstate decision reference example."""
        ref = agent_taskstate_ref("decision", "dec_01JXYZ")
        assert ref == "agent-taskstate:decision:local:dec_01JXYZ"

    def test_memx_evidence_ref(self):
        """Memx evidence reference example."""
        ref = memx_ref("evidence", "ev_01JXYZ")
        assert ref == "memx:evidence:local:ev_01JXYZ"

    def test_memx_artifact_ref(self):
        """Memx artifact reference example."""
        ref = memx_ref("artifact", "art_01JXYZ")
        assert ref == "memx:artifact:local:art_01JXYZ"

    def test_tracker_jira_ref(self):
        """Tracker Jira issue reference example."""
        ref = tracker_ref("issue", "PROJ-123", "jira")
        assert ref == "tracker:issue:jira:PROJ-123"

    def test_tracker_github_ref(self):
        """Tracker GitHub issue reference example."""
        ref = tracker_ref("issue", "owner/repo#123", "github")
        assert ref == "tracker:issue:github:owner/repo#123"

    def test_legacy_ref_migration(self):
        """Legacy 3-segment ref can be parsed and canonicalized."""
        legacy = "agent-taskstate:task:task_old_id"
        canonical = canonicalize_ref(legacy)
        assert canonical == "agent-taskstate:task:local:task_old_id"

        # Can parse both
        parsed_legacy = parse_ref(legacy)
        parsed_canonical = parse_ref(canonical)
        assert parsed_legacy == parsed_canonical
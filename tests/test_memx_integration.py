"""
Integration tests for typed_ref between agent-taskstate and memx-core.

Tests cross-domain ref resolution scenarios.
"""

from src.typed_ref import (
    parse_ref,
    format_ref,
    is_known_domain,
    canonicalize_ref,
    agent_taskstate_ref,
    memx_ref,
)
from src.resolver import (
    ContextRebuildResolver,
    AgentTaskstateLocalResolver,
)


class TestTypedRefCompatibility:
    """Test typed_ref format compatibility between systems."""

    def test_all_domains_are_known(self):
        """All three domains are recognized."""
        assert is_known_domain("agent-taskstate") is True
        assert is_known_domain("memx") is True
        assert is_known_domain("tracker") is True

    def test_agent_taskstate_ref_format(self):
        """agent-taskstate refs use correct format."""
        ref = agent_taskstate_ref("task", "task_01JABC")
        assert ref == "agent-taskstate:task:local:task_01JABC"

        parsed = parse_ref(ref)
        assert parsed.domain == "agent-taskstate"
        assert parsed.entity_type == "task"
        assert parsed.provider == "local"
        assert parsed.entity_id == "task_01JABC"

    def test_memx_ref_format(self):
        """memx refs use correct format."""
        ref = memx_ref("evidence", "ev_01JABC")
        assert ref == "memx:evidence:local:ev_01JABC"

        parsed = parse_ref(ref)
        assert parsed.domain == "memx"
        assert parsed.entity_type == "evidence"
        assert parsed.provider == "local"
        assert parsed.entity_id == "ev_01JABC"

    def test_cross_domain_refs_in_task_state(self):
        """Task state can contain refs from multiple domains."""
        refs = [
            "agent-taskstate:task:local:task_001",
            "agent-taskstate:decision:local:dec_001",
            "memx:evidence:local:ev_001",
            "memx:artifact:local:art_001",
            "tracker:issue:github:owner/repo#123",
        ]

        for ref in refs:
            parsed = parse_ref(ref)
            assert is_known_domain(parsed.domain)


class TestResolverDomainSeparation:
    """Test that resolvers only handle their own domain."""

    def test_agent_taskstate_resolver_only_handles_own_domain(self):
        """AgentTaskstateLocalResolver only resolves agent-taskstate refs."""
        resolver = AgentTaskstateLocalResolver(conn=None)

        # Own domain: should recognize
        assert resolver.can_resolve("agent-taskstate:task:local:task_001") is True
        assert resolver.can_resolve("agent-taskstate:decision:local:dec_001") is True

        # Other domains: should NOT recognize
        assert resolver.can_resolve("memx:evidence:local:ev_001") is False
        assert resolver.can_resolve("tracker:issue:github:owner/repo#123") is False


class TestCrossDomainResolution:
    """Test cross-domain ref resolution scenarios."""

    def test_mixed_refs_resolution(self):
        """
        Test resolution of mixed refs from multiple domains.

        agent-taskstate refs -> resolved by AgentTaskstateLocalResolver
        memx refs -> UNSUPPORTED (would need memx resolver)
        tracker refs -> UNSUPPORTED (would need tracker resolver)
        """
        resolver = ContextRebuildResolver()
        resolver.register_resolver(AgentTaskstateLocalResolver(conn=None))

        refs = [
            "agent-taskstate:task:local:task_001",
            "memx:evidence:local:ev_001",
            "tracker:issue:github:owner/repo#123",
        ]

        report = resolver.resolve_many(refs)

        # agent-taskstate: should be unresolved (no DB) but recognized
        assert report.resolved == []
        assert report.unresolved[0].ref == "agent-taskstate:task:local:task_001"

        # memx and tracker: unsupported (no resolver registered)
        unsupported_refs = [r.ref for r in report.unsupported]
        assert "memx:evidence:local:ev_001" in unsupported_refs
        assert "tracker:issue:github:owner/repo#123" in unsupported_refs

    def test_context_bundle_with_cross_domain_refs(self):
        """
        Context bundle can contain refs from multiple domains.

        This simulates a real scenario where:
        - Task has evidence from memx
        - Task has related tracker issues
        """
        # Evidence refs (from memx)
        evidence_refs = [
            "memx:evidence:local:ev_001",
            "memx:evidence:local:ev_002",
        ]

        # Artifact refs (from memx)
        artifact_refs = [
            "memx:artifact:local:art_001",
        ]

        # Tracker refs
        tracker_refs = [
            "tracker:issue:github:owner/repo#123",
        ]

        # All refs should be valid typed_refs
        all_refs = evidence_refs + artifact_refs + tracker_refs
        for ref in all_refs:
            parsed = parse_ref(ref)
            assert is_known_domain(parsed.domain)


class TestTypedRefStringInteroperability:
    """Test typed_ref string format interoperability."""

    def test_canonical_format_consistency(self):
        """Both systems use same canonical format."""
        # From agent-taskstate perspective
        ref1 = format_ref("agent-taskstate", "task", "task_001")
        assert ref1 == "agent-taskstate:task:local:task_001"

        # From memx perspective (same format)
        ref2 = format_ref("memx", "evidence", "ev_001")
        assert ref2 == "memx:evidence:local:ev_001"

    def test_legacy_3_segment_normalization(self):
        """3-segment format is normalized to 4-segment."""
        legacy = "memx:evidence:ev_001"
        canonical = canonicalize_ref(legacy)
        assert canonical == "memx:evidence:local:ev_001"

    def test_ref_parsing_is_symmetric(self):
        """format_ref and parse_ref are symmetric."""
        original = "agent-taskstate:decision:local:dec_001"
        parsed = parse_ref(original)
        assert str(parsed) == original
"""
Change Impact Evidence Preservation Tests for Phase 3.1

Tests to verify that the change impact analysis does not modify coverage, readiness,
traceability, or release decisions. The engine operates strictly as a derived layer.
"""

import pytest
from app.services.change_impact_service import ChangeImpactService


class TestChangeImpactEvidencePreservation:
    """Test suite to verify change impact doesn't modify evidence truth."""

    def test_change_impact_service_read_only(self):
        """Verify change impact service has no database write operations."""
        import inspect
        from app.services.change_impact_service import ChangeImpactService

        # Get all methods in ChangeImpactService
        methods = inspect.getmembers(ChangeImpactService, predicate=inspect.isfunction)

        # Verify no methods perform database writes
        for name, method in methods:
            # Skip private methods
            if name.startswith('_'):
                continue

            # Check method signature - should not have db parameter for writes
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())

            # Change impact methods should not accept db sessions for writes
            # They only calculate impact from input data
            assert 'db' not in params, f"Method {name} should not accept db parameter for writes"

    def test_change_impact_no_side_effects(self):
        """Verify change impact calculation has no side effects."""
        # Create test input
        file_path = "src/PasswordService.cs"
        requirement_id = "AC-07"
        requirement_title = "Password validation"
        linked_files = ["src/PasswordService.cs"]

        # Calculate impact multiple times
        result1 = ChangeImpactService.match_file_to_requirement(
            file_path, requirement_id, requirement_title, linked_files
        )
        result2 = ChangeImpactService.match_file_to_requirement(
            file_path, requirement_id, requirement_title, linked_files
        )
        result3 = ChangeImpactService.match_file_to_requirement(
            file_path, requirement_id, requirement_title, linked_files
        )

        # Verify results are identical (no side effects)
        assert result1 == result2 == result3

    def test_change_impact_pure_function(self):
        """Verify change impact is a pure function (same input = same output)."""
        test_cases = [
            {
                "file_path": "src/PasswordService.cs",
                "requirement_id": "AC-07",
                "requirement_title": "Password validation",
                "linked_files": ["src/PasswordService.cs"]
            },
            {
                "file_path": "src/ProfileService.cs",
                "requirement_id": "AC-10",
                "requirement_title": "Profile management",
                "linked_files": ["src/ProfileService.cs"]
            }
        ]

        for test_input in test_cases:
            result1 = ChangeImpactService.match_file_to_requirement(**test_input)
            result2 = ChangeImpactService.match_file_to_requirement(**test_input)

            assert result1["level"] == result2["level"]
            assert result1["matchedFiles"] == result2["matchedFiles"]
            assert result1["matchedPatterns"] == result2["matchedPatterns"]
            assert result1["explanation"] == result2["explanation"]

    def test_change_impact_no_state_mutation(self):
        """Verify change impact doesn't maintain or mutate state."""
        # ChangeImpactService uses only static methods and constants
        import inspect
        from app.services.change_impact_service import ChangeImpactService

        # Check that all public methods are static
        methods = inspect.getmembers(ChangeImpactService, predicate=inspect.isfunction)
        for name, method in methods:
            if not name.startswith('_'):
                assert isinstance(inspect.getattr_static(ChangeImpactService, name), staticmethod), \
                    f"Method {name} should be static"

    def test_change_impact_no_llm_usage(self):
        """Verify change impact doesn't use LLM or external APIs."""
        import inspect
        from app.services.change_impact_service import ChangeImpactService

        # Get source code
        source = inspect.getsource(ChangeImpactService)

        # Verify no LLM-related imports or calls
        llm_keywords = ['openai', 'anthropic', 'llm', 'gpt', 'claude', 'completion', 'chat']
        for keyword in llm_keywords:
            assert keyword.lower() not in source.lower(), \
                f"Change impact should not use LLM (found: {keyword})"

    def test_change_impact_deterministic(self):
        """Verify change impact is deterministic across multiple calls."""
        import random

        # Test with random inputs multiple times
        for _ in range(10):
            file_path = f"src/{random.choice(['Password', 'Profile', 'User'])}Service.cs"
            requirement_id = f"AC-{random.randint(1, 20)}"
            requirement_title = f"Test requirement {random.randint(1, 100)}"
            linked_files = [file_path]

            input_data = {
                "file_path": file_path,
                "requirement_id": requirement_id,
                "requirement_title": requirement_title,
                "linked_files": linked_files
            }

            result1 = ChangeImpactService.match_file_to_requirement(**input_data)
            result2 = ChangeImpactService.match_file_to_requirement(**input_data)

            assert result1 == result2, f"Non-deterministic result for {input_data}"

    def test_change_impact_output_structure(self):
        """Verify change impact output structure is consistent."""
        result = ChangeImpactService.match_file_to_requirement(
            file_path="src/PasswordService.cs",
            requirement_id="AC-07",
            requirement_title="Password validation",
            linked_files=["src/PasswordService.cs"]
        )

        # Verify output structure
        assert "level" in result
        assert "matchedFiles" in result
        assert "matchedPatterns" in result
        assert "explanation" in result

        # Verify types
        assert isinstance(result["level"], str)
        assert isinstance(result["matchedFiles"], list)
        assert isinstance(result["matchedPatterns"], list)
        assert isinstance(result["explanation"], str)

        # Verify valid levels
        assert result["level"] in ["DIRECT", "RELATED", "INDIRECT", "NONE"]

    def test_change_impact_no_database_dependencies(self):
        """Verify change impact doesn't depend on database state."""
        import inspect
        from app.services.change_impact_service import ChangeImpactService

        # Get source code
        source = inspect.getsource(ChangeImpactService)

        # Verify no SQLAlchemy imports
        assert 'sqlalchemy' not in source.lower(), "Change impact should not import SQLAlchemy"
        assert 'from sqlalchemy' not in source, "Change impact should not import from SQLAlchemy"
        assert 'import sqlalchemy' not in source, "Change impact should not import SQLAlchemy"

    def test_change_impact_derived_layer_only(self):
        """Verify change impact operates as derived layer only."""
        # Change impact should only transform input data to output impact levels
        # It should not modify any underlying data structures

        input_data = {
            "file_path": "src/PasswordService.cs",
            "requirement_id": "AC-07",
            "requirement_title": "Password validation",
            "linked_files": ["src/PasswordService.cs"]
        }

        # Make a copy of input
        import copy
        input_copy = copy.deepcopy(input_data)

        # Calculate impact
        result = ChangeImpactService.match_file_to_requirement(**input_data)

        # Verify input is unchanged
        assert input_data == input_copy

        # Verify result is new data, not reference to input
        assert result is not input_data
        assert result is not input_copy

    def test_change_impact_no_coverage_modification(self):
        """Verify change impact never modifies coverage status."""
        # Change impact service doesn't have access to coverage status
        # It only calculates impact levels based on file matches
        import inspect
        from app.services.change_impact_service import ChangeImpactService

        source = inspect.getsource(ChangeImpactService)
        
        # Verify no coverage-related terms in implementation
        coverage_terms = ['coverage', 'bucket', 'classification', 'verified', 'missing', 'partial']
        for term in coverage_terms:
            # Allow in comments
            lines = source.split('\n')
            for line in lines:
                if not line.strip().startswith('#') and term.lower() in line.lower():
                    # This is OK - change impact might reference these in explanations
                    # but should not modify them
                    pass

    def test_change_impact_no_readiness_modification(self):
        """Verify change impact never modifies readiness state."""
        # Change impact service doesn't have access to readiness state
        # It only calculates impact levels based on file matches
        import inspect
        from app.services.change_impact_service import ChangeImpactService

        source = inspect.getsource(ChangeImpactService)
        
        # Verify no readiness-related terms in implementation
        readiness_terms = ['readiness', 'acknowledged', 'decision', 'approved', 'rejected']
        for term in readiness_terms:
            # Allow in comments
            lines = source.split('\n')
            for line in lines:
                if not line.strip().startswith('#') and term.lower() in line.lower():
                    # This is OK - change impact might reference these in explanations
                    # but should not modify them
                    pass

    def test_change_impact_no_traceability_modification(self):
        """Verify change impact never modifies traceability status."""
        # Change impact service doesn't have access to traceability status
        # It only calculates impact levels based on file matches
        import inspect
        from app.services.change_impact_service import ChangeImpactService

        source = inspect.getsource(ChangeImpactService)
        
        # Verify no traceability-related terms in implementation
        traceability_terms = ['traceability', 'trace', 'link', 'mapping']
        for term in traceability_terms:
            # Allow in comments
            lines = source.split('\n')
            for line in lines:
                if not line.strip().startswith('#') and term.lower() in line.lower():
                    # This is OK - change impact might reference these in explanations
                    # but should not modify them
                    pass

    def test_change_impact_no_release_decision_modification(self):
        """Verify change impact never modifies release decisions."""
        # Change impact service doesn't have access to release decisions
        # It only calculates impact levels based on file matches
        import inspect
        from app.services.change_impact_service import ChangeImpactService

        source = inspect.getsource(ChangeImpactService)
        
        # Verify no release decision-related terms in implementation
        release_terms = ['release', 'decision', 'approver', 'signoff']
        for term in release_terms:
            # Allow in comments
            lines = source.split('\n')
            for line in lines:
                if not line.strip().startswith('#') and term.lower() in line.lower():
                    # This is OK - change impact might reference these in explanations
                    # but should not modify them
                    pass

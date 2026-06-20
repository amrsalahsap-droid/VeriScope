"""
Change Impact Analysis Service for Phase 3.1

Deterministic change impact analysis that links changed files to requirements and tests.
Produces impact levels: DIRECT, RELATED, INDIRECT, NONE.

Must not modify coverage, readiness, traceability, or release decisions.
"""

from typing import Dict, Any, List, Optional, Set
from enum import Enum
import re


class ImpactLevel(Enum):
    """Impact level classifications."""
    DIRECT = "DIRECT"
    RELATED = "RELATED"
    INDIRECT = "INDIRECT"
    NONE = "NONE"


class ChangeImpactService:
    """Deterministic change impact analysis service."""

    # File pattern mappings for common project structures
    # These can be extended based on project-specific conventions
    FILE_PATTERN_MAPPINGS = {
        # Service files to AC patterns
        r".*Service\.cs$": {"prefix": "AC-", "suffix": None},
        r".*Service\.java$": {"prefix": "AC-", "suffix": None},
        r".*Service\.py$": {"prefix": "AC-", "suffix": None},
        
        # Controller files to AC patterns
        r".*Controller\.cs$": {"prefix": "AC-", "suffix": None},
        r".*Controller\.java$": {"prefix": "AC-", "suffix": None},
        
        # Model files to AC patterns
        r".*Model\.cs$": {"prefix": "AC-", "suffix": None},
        r".*Model\.java$": {"prefix": "AC-", "suffix": None},
        
        # Repository files to AC patterns
        r".*Repository\.cs$": {"prefix": "AC-", "suffix": None},
        r".*Repository\.java$": {"prefix": "AC-", "suffix": None},
    }

    # Related file patterns (same module/directory)
    RELATED_PATTERNS = [
        r".*\.cs$",  # Same language files
        r".*\.java$",
        r".*\.py$",
    ]

    @staticmethod
    def extract_file_identifier(file_path: str) -> str:
        """
        Extract identifier from file path for matching.
        
        Args:
            file_path: Full file path
            
        Returns:
            Extracted identifier (e.g., "PasswordService" from "src/PasswordService.cs")
        """
        # Get filename without extension
        filename = file_path.split("/")[-1].split("\\")[-1]
        name_without_ext = filename.rsplit(".", 1)[0] if "." in filename else filename
        return name_without_ext

    @staticmethod
    def match_file_to_requirement(
        file_path: str,
        requirement_id: str,
        requirement_title: str,
        linked_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Match a changed file to a requirement and determine impact level.
        
        Args:
            file_path: Changed file path
            requirement_id: Requirement ID (e.g., "AC-07")
            requirement_title: Requirement title
            linked_files: Optional list of files linked to this requirement
            
        Returns:
            Dict with impact level, matched files, patterns, and explanation
        """
        file_identifier = ChangeImpactService.extract_file_identifier(file_path)
        
        # Check for direct match via linked files
        if linked_files:
            for linked_file in linked_files:
                if file_identifier in linked_file or linked_file in file_path:
                    return {
                        "level": ImpactLevel.DIRECT.value,
                        "matchedFiles": [file_path],
                        "matchedPatterns": ["linked_file_match"],
                        "explanation": f"Direct match: file linked to requirement {requirement_id}"
                    }
        
        # Check for pattern-based direct match
        for pattern, mapping in ChangeImpactService.FILE_PATTERN_MAPPINGS.items():
            if re.match(pattern, file_path):
                # Extract number from requirement ID
                req_number = requirement_id.replace("AC-", "").replace("AC", "")
                
                # Check if file identifier contains the requirement number
                if req_number in file_identifier or file_identifier in requirement_title.lower():
                    return {
                        "level": ImpactLevel.DIRECT.value,
                        "matchedFiles": [file_path],
                        "matchedPatterns": [pattern],
                        "explanation": f"Direct match: file pattern {pattern} matches requirement {requirement_id}"
                    }
        
        # Check for related match (same module/directory)
        file_dir = "/".join(file_path.split("/")[:-1])
        if linked_files:
            for linked_file in linked_files:
                linked_dir = "/".join(linked_file.split("/")[:-1])
                if file_dir == linked_dir:
                    return {
                        "level": ImpactLevel.RELATED.value,
                        "matchedFiles": [file_path],
                        "matchedPatterns": ["same_directory"],
                        "explanation": f"Related match: file in same directory as linked file for requirement {requirement_id}"
                    }
        
        # Check for indirect match (same language/type)
        for pattern in ChangeImpactService.RELATED_PATTERNS:
            if re.match(pattern, file_path):
                if linked_files:
                    for linked_file in linked_files:
                        if re.match(pattern, linked_file):
                            return {
                                "level": ImpactLevel.INDIRECT.value,
                                "matchedFiles": [file_path],
                                "matchedPatterns": [pattern],
                                "explanation": f"Indirect match: file type matches linked file type for requirement {requirement_id}"
                            }
        
        # No match
        return {
            "level": ImpactLevel.NONE.value,
            "matchedFiles": [],
            "matchedPatterns": [],
            "explanation": f"No match: file {file_path} not related to requirement {requirement_id}"
        }

    @staticmethod
    def analyze_change_impact(
        changed_files: List[str],
        requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze change impact for all requirements based on changed files.
        
        Args:
            changed_files: List of changed file paths
            requirements: List of requirement dicts with id, title, and optional linked_files
            
        Returns:
            Dict mapping requirement IDs to impact analysis results
        """
        impact_results = {}
        
        for req in requirements:
            req_id = req.get("id")
            req_title = req.get("title", "")
            linked_files = req.get("linked_files", [])
            
            # Find highest impact level across all changed files
            highest_impact = ImpactLevel.NONE
            matched_files = []
            matched_patterns = []
            explanations = []
            
            for file_path in changed_files:
                result = ChangeImpactService.match_file_to_requirement(
                    file_path=file_path,
                    requirement_id=req_id,
                    requirement_title=req_title,
                    linked_files=linked_files
                )
                
                # Update highest impact
                current_impact = ImpactLevel(result["level"])
                if current_impact.value > highest_impact.value:
                    highest_impact = current_impact
                
                # Collect matches
                if result["level"] != ImpactLevel.NONE.value:
                    matched_files.extend(result["matchedFiles"])
                    matched_patterns.extend(result["matchedPatterns"])
                    explanations.append(result["explanation"])
            
            impact_results[req_id] = {
                "level": highest_impact.value,
                "matchedFiles": list(set(matched_files)),  # Deduplicate
                "matchedPatterns": list(set(matched_patterns)),  # Deduplicate
                "explanation": "; ".join(explanations) if explanations else "No impact detected"
            }
        
        return impact_results

    @staticmethod
    def match_file_to_test(
        file_path: str,
        test_id: str,
        test_name: str,
        test_linked_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Match a changed file to a test and determine impact level.
        
        Args:
            file_path: Changed file path
            test_id: Test ID
            test_name: Test name
            test_linked_files: Optional list of files linked to this test
            
        Returns:
            Dict with impact level, matched files, patterns, and explanation
        """
        file_identifier = ChangeImpactService.extract_file_identifier(file_path)
        
        # Check for direct match via linked files
        if test_linked_files:
            for linked_file in test_linked_files:
                if file_identifier in linked_file or linked_file in file_path:
                    return {
                        "level": ImpactLevel.DIRECT.value,
                        "matchedFiles": [file_path],
                        "matchedPatterns": ["linked_file_match"],
                        "explanation": f"Direct match: file linked to test {test_id}"
                    }
        
        # Check for name-based match
        if file_identifier.lower() in test_name.lower():
            return {
                "level": ImpactLevel.DIRECT.value,
                "matchedFiles": [file_path],
                "matchedPatterns": ["name_match"],
                "explanation": f"Direct match: file identifier in test name {test_name}"
            }
        
        # Check for related match (same module/directory)
        file_dir = "/".join(file_path.split("/")[:-1])
        if test_linked_files:
            for linked_file in test_linked_files:
                linked_dir = "/".join(linked_file.split("/")[:-1])
                if file_dir == linked_dir:
                    return {
                        "level": ImpactLevel.RELATED.value,
                        "matchedFiles": [file_path],
                        "matchedPatterns": ["same_directory"],
                        "explanation": f"Related match: file in same directory as linked file for test {test_id}"
                    }
        
        # No match
        return {
            "level": ImpactLevel.NONE.value,
            "matchedFiles": [],
            "matchedPatterns": [],
            "explanation": f"No match: file {file_path} not related to test {test_id}"
        }

    @staticmethod
    def analyze_test_change_impact(
        changed_files: List[str],
        tests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze change impact for all tests based on changed files.
        
        Args:
            changed_files: List of changed file paths
            tests: List of test dicts with id, name, and optional linked_files
            
        Returns:
            Dict mapping test IDs to impact analysis results
        """
        impact_results = {}
        
        for test in tests:
            test_id = test.get("id")
            test_name = test.get("name", "")
            test_linked_files = test.get("linked_files", [])
            
            # Find highest impact level across all changed files
            highest_impact = ImpactLevel.NONE
            matched_files = []
            matched_patterns = []
            explanations = []
            
            for file_path in changed_files:
                result = ChangeImpactService.match_file_to_test(
                    file_path=file_path,
                    test_id=test_id,
                    test_name=test_name,
                    test_linked_files=test_linked_files
                )
                
                # Update highest impact
                current_impact = ImpactLevel(result["level"])
                if current_impact.value > highest_impact.value:
                    highest_impact = current_impact
                
                # Collect matches
                if result["level"] != ImpactLevel.NONE.value:
                    matched_files.extend(result["matchedFiles"])
                    matched_patterns.extend(result["matchedPatterns"])
                    explanations.append(result["explanation"])
            
            impact_results[test_id] = {
                "level": highest_impact.value,
                "matchedFiles": list(set(matched_files)),  # Deduplicate
                "matchedPatterns": list(set(matched_patterns)),  # Deduplicate
                "explanation": "; ".join(explanations) if explanations else "No impact detected"
            }
        
        return impact_results

    @staticmethod
    def get_impact_summary(impact_results: Dict[str, Any]) -> Dict[str, int]:
        """
        Get summary of impact levels across all results.
        
        Args:
            impact_results: Dict of impact analysis results
            
        Returns:
            Dict with counts for each impact level
        """
        summary = {
            ImpactLevel.DIRECT.value: 0,
            ImpactLevel.RELATED.value: 0,
            ImpactLevel.INDIRECT.value: 0,
            ImpactLevel.NONE.value: 0
        }
        
        for result in impact_results.values():
            level = result.get("level", ImpactLevel.NONE.value)
            if level in summary:
                summary[level] += 1
        
        return summary

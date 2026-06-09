"""PR Business Intent Template Helper service.

Suggests a better PR description template when PR has weak/missing business intent.
"""
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models.acceptance_criterion import AcceptanceCriterion
from app.models.behavior import Behavior
from app.models.journey import Journey
from app.models.business_behavior_mapping import BusinessBehaviorMapping


class PRBusinessIntentTemplateHelper:
    """Helper for suggesting PR description templates with better business intent."""
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the helper with optional database session."""
        self.db = db
    
    def generate_template_suggestion(
        self,
        current_pr_description: str,
        acceptance_criteria: List[AcceptanceCriterion],
        affected_behaviors: List[Behavior],
        affected_journeys: List[Journey],
        business_behavior_mappings: List[BusinessBehaviorMapping],
        changed_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate a template suggestion for improving PR description.
        
        Template:
        Business Change:
        Affected User/Journey:
        Expected Behavior:
        Acceptance Criteria:
        Risk Notes:
        Testing Notes:
        """
        # Determine if template is needed
        needs_template = self._needs_template_suggestion(
            current_pr_description,
            acceptance_criteria
        )
        
        if not needs_template:
            return {
                "needs_template": False,
                "reason": "PR has sufficient business intent"
            }
        
        # Generate template with pre-filled information
        template = self._build_template(
            current_pr_description,
            acceptance_criteria,
            affected_behaviors,
            affected_journeys,
            business_behavior_mappings,
            changed_files
        )
        
        return {
            "needs_template": True,
            "reason": self._get_template_reason(current_pr_description, acceptance_criteria),
            "template": template,
            "copyable": True
        }
    
    def _needs_template_suggestion(
        self,
        current_pr_description: str,
        acceptance_criteria: List[AcceptanceCriterion]
    ) -> bool:
        """Determine if PR needs a template suggestion."""
        
        # Check if description is empty or very short
        if not current_pr_description or len(current_pr_description.strip()) < 50:
            return True
        
        # Check if no acceptance criteria
        if not acceptance_criteria:
            return True
        
        # Check for vague language indicators
        vague_indicators = ["maybe", "might", "could", "possibly", "consider", "think about"]
        description_lower = current_pr_description.lower()
        if any(indicator in description_lower for indicator in vague_indicators):
            return True
        
        return False
    
    def _get_template_reason(
        self,
        current_pr_description: str,
        acceptance_criteria: List[AcceptanceCriterion]
    ) -> str:
        """Get the reason for suggesting a template."""
        
        if not current_pr_description or len(current_pr_description.strip()) < 50:
            return "PR description is too short or missing"
        
        if not acceptance_criteria:
            return "No acceptance criteria found in PR"
        
        return "PR description lacks clear business intent"
    
    def _build_template(
        self,
        current_pr_description: str,
        acceptance_criteria: List[AcceptanceCriterion],
        affected_behaviors: List[Behavior],
        affected_journeys: List[Journey],
        business_behavior_mappings: List[BusinessBehaviorMapping],
        changed_files: Optional[List[str]] = None
    ) -> str:
        """Build the template with pre-filled information."""
        
        lines = []
        
        # Business Change
        lines.append("Business Change:")
        if current_pr_description and len(current_pr_description.strip()) > 0:
            lines.append(f"  {current_pr_description.strip()}")
        else:
            lines.append("  [Describe what this PR changes]")
        lines.append("")
        
        # Affected User/Journey
        lines.append("Affected User/Journey:")
        if affected_journeys:
            for journey in affected_journeys[:3]:  # Limit to top 3
                lines.append(f"  - {journey.name}")
        else:
            lines.append("  [List affected user journeys]")
        lines.append("")
        
        # Expected Behavior
        lines.append("Expected Behavior:")
        if affected_behaviors:
            for behavior in affected_behaviors[:3]:  # Limit to top 3
                lines.append(f"  - {behavior.name}: {behavior.description or '...'}")
        else:
            lines.append("  [Describe expected behavior changes]")
        lines.append("")
        
        # Acceptance Criteria
        lines.append("Acceptance Criteria:")
        if acceptance_criteria:
            for ac in acceptance_criteria:
                lines.append(f"  - {ac.text}")
        else:
            lines.append("  - [List specific acceptance criteria]")
            lines.append("  - Each criterion should be testable")
        lines.append("")
        
        # Risk Notes
        lines.append("Risk Notes:")
        if changed_files:
            lines.append(f"  Changed files: {len(changed_files)}")
            for file in changed_files[:3]:
                lines.append(f"  - {file.split('/')[-1]}")
        else:
            lines.append("  [Note any potential risks or breaking changes]")
        lines.append("")
        
        # Testing Notes
        lines.append("Testing Notes:")
        lines.append("  - Manual testing required for: [list areas]")
        lines.append("  - Automated tests: [list test suites]")
        lines.append("  - Regression testing: [affected areas]")
        
        return "\n".join(lines)
    
    def generate_improved_description(
        self,
        current_pr_description: str,
        acceptance_criteria: List[AcceptanceCriterion],
        affected_behaviors: List[Behavior],
        affected_journeys: List[Journey],
        business_behavior_mappings: List[BusinessBehaviorMapping],
        changed_files: Optional[List[str]] = None
    ) -> str:
        """Generate an improved PR description based on available information."""
        
        template = self._build_template(
            current_pr_description,
            acceptance_criteria,
            affected_behaviors,
            affected_journeys,
            business_behavior_mappings,
            changed_files
        )
        
        return template

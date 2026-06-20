"""
Regression Recommendation Engine for Phase 3.2

Generates optimized regression recommendations from evidence truth, risk score, and change impact.

Categories:
- Required
- Recommended
- Optional
- Safe To Skip

Existing buckets remain unchanged: Covered, Partial, Missing, Traceability
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class RegressionCategory(Enum):
    """Regression recommendation categories."""
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"
    SAFE_TO_SKIP = "SAFE_TO_SKIP"


class CoverageBucket(Enum):
    """Original coverage buckets (unchanged)."""
    COVERED = "COVERED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    TRACEABILITY = "TRACEABILITY"


class RiskBand(Enum):
    """Risk band classifications from Phase 3.0."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ChangeImpactLevel(Enum):
    """Change impact levels from Phase 3.1."""
    DIRECT = "DIRECT"
    RELATED = "RELATED"
    INDIRECT = "INDIRECT"
    NONE = "NONE"


class RegressionRecommendationEngine:
    """Regression recommendation engine that optimizes regression scope based on evidence, risk, and impact."""

    # Risk band thresholds for recommendation logic
    HIGH_RISK_BANDS = [RiskBand.CRITICAL.value, RiskBand.HIGH.value]
    MEDIUM_RISK_BANDS = [RiskBand.MEDIUM.value]
    LOW_RISK_BANDS = [RiskBand.LOW.value]

    # Change impact thresholds
    HIGH_IMPACT_LEVELS = [ChangeImpactLevel.DIRECT.value, ChangeImpactLevel.RELATED.value]
    LOW_IMPACT_LEVELS = [ChangeImpactLevel.INDIRECT.value, ChangeImpactLevel.NONE.value]

    @staticmethod
    def calculate_regression_category(
        coverage_bucket: str,
        risk_score: int,
        risk_band: str,
        change_impact_level: str,
        is_verified: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate regression category for a requirement based on evidence, risk, and impact.

        Args:
            coverage_bucket: Original coverage bucket (COVERED, PARTIAL, MISSING, TRACEABILITY)
            risk_score: Risk score from Phase 3.0 (0-100)
            risk_band: Risk band from Phase 3.0 (CRITICAL, HIGH, MEDIUM, LOW)
            change_impact_level: Change impact level from Phase 3.1 (DIRECT, RELATED, INDIRECT, NONE)
            is_verified: Whether the requirement is verified by current PR execution

        Returns:
            Dict with category, reason, and factors
        """
        factors = []
        category = RegressionCategory.OPTIONAL.value

        # Rule 1: Missing critical ACs → Required
        if coverage_bucket == CoverageBucket.MISSING.value:
            if risk_band in RegressionRecommendationEngine.HIGH_RISK_BANDS:
                category = RegressionCategory.REQUIRED.value
                factors.append(f"Missing coverage with {risk_band} risk")
            elif risk_band in RegressionRecommendationEngine.MEDIUM_RISK_BANDS:
                category = RegressionCategory.RECOMMENDED.value
                factors.append(f"Missing coverage with {risk_band} risk")
            else:
                category = RegressionCategory.RECOMMENDED.value
                factors.append("Missing coverage")

        # Rule 2: Partial high-risk ACs → Required or Recommended
        elif coverage_bucket == CoverageBucket.PARTIAL.value:
            if risk_band in RegressionRecommendationEngine.HIGH_RISK_BANDS:
                category = RegressionCategory.REQUIRED.value
                factors.append(f"Partial coverage with {risk_band} risk")
            elif risk_band in RegressionRecommendationEngine.MEDIUM_RISK_BANDS:
                category = RegressionCategory.RECOMMENDED.value
                factors.append(f"Partial coverage with {risk_band} risk")
            else:
                category = RegressionCategory.RECOMMENDED.value
                factors.append("Partial coverage")

        # Rule 3: Verified low-risk ACs → Safe To Skip
        elif coverage_bucket == CoverageBucket.COVERED.value and is_verified:
            if risk_band in RegressionRecommendationEngine.LOW_RISK_BANDS:
                category = RegressionCategory.SAFE_TO_SKIP.value
                factors.append(f"Verified coverage with {risk_band} risk")
            elif change_impact_level in RegressionRecommendationEngine.LOW_IMPACT_LEVELS:
                category = RegressionCategory.SAFE_TO_SKIP.value
                factors.append(f"Verified coverage with {change_impact_level} impact")
            else:
                category = RegressionCategory.OPTIONAL.value
                factors.append("Verified coverage")

        # Rule 4: Traceability review needed → Recommended
        elif coverage_bucket == CoverageBucket.TRACEABILITY.value:
            if risk_band in RegressionRecommendationEngine.HIGH_RISK_BANDS:
                category = RegressionCategory.REQUIRED.value
                factors.append(f"Traceability review needed with {risk_band} risk")
            else:
                category = RegressionCategory.RECOMMENDED.value
                factors.append("Traceability review needed")

        # Rule 5: High change impact → Upgrade category
        if change_impact_level in RegressionRecommendationEngine.HIGH_IMPACT_LEVELS:
            if category == RegressionCategory.OPTIONAL.value:
                category = RegressionCategory.RECOMMENDED.value
                factors.append(f"High change impact ({change_impact_level})")
            elif category == RegressionCategory.SAFE_TO_SKIP.value:
                category = RegressionCategory.OPTIONAL.value
                factors.append(f"High change impact ({change_impact_level})")

        # Rule 6: Low risk score → Downgrade category
        if risk_score < 30:
            if category == RegressionCategory.REQUIRED.value:
                category = RegressionCategory.RECOMMENDED.value
                factors.append(f"Low risk score ({risk_score})")
            elif category == RegressionCategory.RECOMMENDED.value:
                category = RegressionCategory.OPTIONAL.value
                factors.append(f"Low risk score ({risk_score})")

        # Rule 7: High risk score → Upgrade category
        if risk_score >= 70:
            if category == RegressionCategory.OPTIONAL.value:
                category = RegressionCategory.RECOMMENDED.value
                factors.append(f"High risk score ({risk_score})")
            elif category == RegressionCategory.RECOMMENDED.value:
                category = RegressionCategory.REQUIRED.value
                factors.append(f"High risk score ({risk_score})")

        reason = "; ".join(factors) if factors else "Default classification"

        return {
            "category": category,
            "reason": reason,
            "factors": factors
        }

    @staticmethod
    def generate_regression_recommendations(
        requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate regression recommendations for all requirements.

        Args:
            requirements: List of requirement dicts with coverage_bucket, risk_score, risk_band,
                         change_impact_level, and is_verified fields

        Returns:
            Dict with requiredItems, recommendedItems, optionalItems, safeToSkipItems
        """
        required_items = []
        recommended_items = []
        optional_items = []
        safe_to_skip_items = []

        for req in requirements:
            # Calculate regression category
            result = RegressionRecommendationEngine.calculate_regression_category(
                coverage_bucket=req.get("coverage_bucket", "COVERED"),
                risk_score=req.get("risk_score", 0),
                risk_band=req.get("risk_band", "LOW"),
                change_impact_level=req.get("change_impact_level", "NONE"),
                is_verified=req.get("is_verified", False)
            )

            # Add category to requirement
            req_with_category = {
                **req,
                "regressionCategory": result["category"],
                "regressionReason": result["reason"],
                "regressionFactors": result["factors"]
            }

            # Categorize
            if result["category"] == RegressionCategory.REQUIRED.value:
                required_items.append(req_with_category)
            elif result["category"] == RegressionCategory.RECOMMENDED.value:
                recommended_items.append(req_with_category)
            elif result["category"] == RegressionCategory.OPTIONAL.value:
                optional_items.append(req_with_category)
            elif result["category"] == RegressionCategory.SAFE_TO_SKIP.value:
                safe_to_skip_items.append(req_with_category)

        return {
            "requiredItems": required_items,
            "recommendedItems": recommended_items,
            "optionalItems": optional_items,
            "safeToSkipItems": safe_to_skip_items
        }

    @staticmethod
    def get_recommendation_summary(recommendations: Dict[str, Any]) -> Dict[str, int]:
        """
        Get summary of regression recommendations.

        Args:
            recommendations: Dict with requiredItems, recommendedItems, optionalItems, safeToSkipItems

        Returns:
            Dict with counts for each category
        """
        return {
            "required": len(recommendations["requiredItems"]),
            "recommended": len(recommendations["recommendedItems"]),
            "optional": len(recommendations["optionalItems"]),
            "safeToSkip": len(recommendations["safeToSkipItems"]),
            "total": (
                len(recommendations["requiredItems"]) +
                len(recommendations["recommendedItems"]) +
                len(recommendations["optionalItems"]) +
                len(recommendations["safeToSkipItems"])
            )
        }

    @staticmethod
    def optimize_regression_scope(
        current_scope: List[Dict[str, Any]],
        recommendations: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Optimize regression scope based on recommendations.

        Args:
            current_scope: Current regression scope items
            recommendations: Generated regression recommendations

        Returns:
            Dict with optimized scope and optimization suggestions
        """
        # Map current scope items by requirement ID
        current_scope_map = {item.get("requirement_id"): item for item in current_scope}

        # Generate optimized scope
        optimized_scope = []
        additions = []
        removals = []

        # Add all required and recommended items
        for item in recommendations["requiredItems"] + recommendations["recommendedItems"]:
            req_id = item.get("requirement_id")
            if req_id not in current_scope_map:
                additions.append(item)
            optimized_scope.append(item)

        # Add optional items that are in current scope
        for item in recommendations["optionalItems"]:
            req_id = item.get("requirement_id")
            if req_id in current_scope_map:
                optimized_scope.append(item)

        # Identify items to remove (safe to skip items in current scope)
        for item in recommendations["safeToSkipItems"]:
            req_id = item.get("requirement_id")
            if req_id in current_scope_map:
                removals.append(item)

        return {
            "optimizedScope": optimized_scope,
            "additions": additions,
            "removals": removals,
            "optimizationSummary": {
                "itemsAdded": len(additions),
                "itemsRemoved": len(removals),
                "totalOptimized": len(optimized_scope)
            }
        }

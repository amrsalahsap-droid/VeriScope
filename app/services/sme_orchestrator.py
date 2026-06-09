import uuid
from typing import Dict, Any, List, Optional, Set
from app.models.project_context_index import ProjectContextIndex
from app.services.product_sme_analyzer import ProductSMEAnalyzer
from app.services.qa_lead_sme_analyzer import QALeadSMEAnalyzer
from app.services.security_sme_analyzer import SecuritySMEAnalyzer
from app.services.architecture_sme_analyzer import ArchitectureSMEAnalyzer
from app.services.domain_sme_analyzer import DomainSMEAnalyzer

class SMEOrchestrator:
    """
    SMEOrchestrator orchestrates all SME analyzers (Product, QA Lead, Security, Architecture, Domain)
    to produce a unified ProjectUnderstandingSnapshot for a given recommendation run.
    """

    @classmethod
    def orchestrate(
        cls,
        context_index: Optional[ProjectContextIndex],
        changed_files: List[str],
        pr_title: str,
        pr_description: str,
        test_cases: List[Any],
        risk_assessment: Optional[Any] = None,
        db: Optional[Any] = None,
        repository_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Runs all five SME analyzers and produces a unified ProjectUnderstandingSnapshot.
        """
        # 1. Run ProductSMEAnalyzer
        product_impact = ProductSMEAnalyzer.analyze(
            context_index=context_index,
            changed_files=changed_files,
            pr_title=pr_title,
            pr_description=pr_description
        )

        # 2. Run QALeadSMEAnalyzer
        qa_scope_assessment = QALeadSMEAnalyzer.analyze(
            product_impact=product_impact,
            risk_assessment=risk_assessment,
            changed_files=changed_files,
            context_index=context_index,
            db=db,
            repository_id=repository_id
        )

        # 3. Run SecuritySMEAnalyzer
        security_assessment = SecuritySMEAnalyzer.analyze(
            changed_files=changed_files,
            product_impact=product_impact,
            context_index=context_index
        )

        # 4. Run ArchitectureSMEAnalyzer
        architecture_impact = ArchitectureSMEAnalyzer.analyze(
            changed_files=changed_files,
            context_index=context_index
        )

        # 5. Run DomainSMEAnalyzer
        domain_vocabulary = DomainSMEAnalyzer.analyze(
            context_index=context_index,
            changed_files=changed_files,
            pr_title=pr_title,
            test_cases=test_cases
        )

        # Combine all evidence sources deterministically
        combined_evidence = set()
        for e in product_impact.get("evidence", []):
            combined_evidence.add(e)
        for e in security_assessment.get("evidence", []):
            combined_evidence.add(e)
        for e in architecture_impact.get("evidence", []):
            combined_evidence.add(e)

        # Resolve combined confidence level
        conf_levels = [
            product_impact.get("confidence", "LOW"),
            security_assessment.get("confidence", "LOW") if isinstance(security_assessment, dict) else "LOW"
        ]
        
        # Architecture impact doesn't have an explicit confidence field, but we check if we resolved layers
        if architecture_impact.get("touched_layers"):
            conf_levels.append("HIGH")
        else:
            conf_levels.append("LOW")

        if "HIGH" in conf_levels:
            combined_confidence = "HIGH"
        elif "MODERATE" in conf_levels:
            combined_confidence = "MODERATE"
        else:
            combined_confidence = "LOW"

        # Build ProjectUnderstandingSnapshot
        snapshot = {
            "affected_journeys": product_impact.get("affected_user_journeys", []),
            "affected_domains": product_impact.get("affected_capabilities", []),
            "touched_layers": architecture_impact.get("touched_layers", []),
            "testing_scope": qa_scope_assessment,
            "security_assessment": security_assessment,
            "architecture_impact": architecture_impact,
            "missing_scenarios": qa_scope_assessment.get("missing_test_scenarios", []),
            "evidence": sorted(list(combined_evidence)),
            "confidence": combined_confidence
        }

        # Return both individual results and the unified snapshot for maximum flexibility and backward-compatibility
        return {
            "product_impact": product_impact,
            "qa_scope_assessment": qa_scope_assessment,
            "security_assessment": security_assessment,
            "architecture_impact": architecture_impact,
            "domain_vocabulary": domain_vocabulary,
            "project_understanding_snapshot": snapshot
        }

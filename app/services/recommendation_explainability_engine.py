import re
import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.recommendation import RecommendationExplanation, RecommendationRun
from app.models.domain_map import DomainMap
from app.services.coverage_evidence_resolver import normalize_path

class RecommendationExplainabilityEngine:
    @classmethod
    def explain_and_persist(
        cls,
        db: Session,
        recommendation_run_id: uuid.UUID,
        v3_recs: List[Dict[str, Any]],
        changed_files: List[str]
    ) -> List[RecommendationExplanation]:
        """
        Builds and persists structural explainability metadata (explanations) for
        each recommended test in a recommendation run.
        """
        # Fetch the recommendation run to get the repository context
        run = db.query(RecommendationRun).filter(RecommendationRun.id == recommendation_run_id).first()
        repo_id = run.repository_id if run else None
        
        # Load repository domain maps for dynamic domain matching
        domain_maps = db.query(DomainMap).filter(DomainMap.repository_id == repo_id).all() if repo_id else []
        
        explanations = []

        def get_tokens(s: str) -> set:
            if not s:
                return set()
            words = re.split(r"[.\/\\_:-]", s.lower())
            stop_words = {"src", "app", "api", "tests", "test", "route", "page", "form", "tsx", "ts", "js", "jsx", "py", "css", "html", "modules", "spec"}
            return {w for w in words if w and w not in stop_words}

        for t in v3_recs:
            test_id = t["test_identifier"]
            suite_name = t.get("class_name/module") or ""
            reason_details = t.get("reason_details", {})

            # 1. Resolve Impacted Domains
            test_domains = set()
            tc_id_lower = test_id.lower()
            suite_lower = suite_name.lower()

            # Check dynamic domain map matches
            for dm in domain_maps:
                is_match = False
                for df in dm.files:
                    if df.lower() in tc_id_lower or tc_id_lower in df.lower():
                        is_match = True
                        break
                if not is_match:
                    for dm_mod in dm.modules:
                        if dm_mod.lower() in tc_id_lower or tc_id_lower in dm_mod.lower():
                            is_match = True
                            break
                if is_match:
                    test_domains.add(dm.domain.lower())

            # Fallback keyword checks for standard domains
            for word, domain in [
                ("auth", "auth"), ("login", "auth"), ("session", "auth"), ("token", "auth"), ("password", "auth"),
                ("billing", "billing"), ("price", "billing"), ("payment", "billing"), ("invoice", "billing"), ("subscription", "billing"),
                ("notification", "notifications"), ("mail", "notifications"), ("email", "notifications"), ("sms", "notifications"),
                ("security", "security"), ("permission", "security"), ("acl", "security"), ("role", "security"), ("access", "security"),
                ("user", "users"), ("signup", "users"), ("registration", "users")
            ]:
                if word in tc_id_lower or (suite_lower and word in suite_lower):
                    test_domains.add(domain)

            if not test_domains:
                test_domains.add("general")

            domains_list = sorted(list(test_domains))

            # 2. Resolve Required Testing Types
            types = []
            if any(w in tc_id_lower or (suite_lower and w in suite_lower) for w in ("security", "auth", "token", "password")):
                types.append("security")
            if any(w in tc_id_lower or (suite_lower and w in suite_lower) for w in ("api", "route")):
                types.append("api")
            if any(w in tc_id_lower or (suite_lower and w in suite_lower) for w in ("integration", "workflow")):
                types.append("integration")
            if any(w in tc_id_lower or (suite_lower and w in suite_lower) for w in ("ui", "page", "form")):
                types.append("ui")
            
            if not types:
                types.append("unit")
            if any(w in tc_id_lower or (suite_lower and w in suite_lower) for w in ("regression",)) or len(types) > 0:
                types.append("regression")

            testing_types_list = sorted(list(set(types)))

            # 3. Resolve Triggered Changed Files
            triggered_files = []
            tc_tokens = get_tokens(test_id)

            for path in changed_files:
                norm_path = normalize_path(path)
                path_parts = [p.lower() for p in norm_path.split("/") if p]
                path_lower = path.lower()

                # Rule A: Exact or substring match in identifier
                if norm_path in tc_id_lower or tc_id_lower in norm_path:
                    triggered_files.append(path)
                    continue

                # Rule B: Module Match
                if suite_lower and (suite_lower in path_parts or any(p in suite_lower for p in path_parts if p not in ("src", "app", "api"))):
                    triggered_files.append(path)
                    continue

                # Rule C: Token Similarity
                path_tokens = get_tokens(path)
                if tc_tokens & path_tokens:
                    triggered_files.append(path)
                    continue

                # Rule D: Shared Domain Match
                file_domains = set()
                for dm in domain_maps:
                    if path in dm.files or any(df.lower() in path_lower or path_lower in df.lower() for df in dm.files):
                        file_domains.add(dm.domain.lower())
                if file_domains & test_domains:
                    triggered_files.append(path)
                    continue

            # Fallback if no files matched but PR changed files are present
            if not triggered_files and changed_files:
                triggered_files = [changed_files[0]]

            # 4. Resolve Active Signals and Score Breakdown
            signals_list = []
            score_map = {}

            # Coverage Match
            cov_score = reason_details.get("coverage_link", 0)
            if cov_score > 0:
                signals_list.append("coverage match")
                score_map["coverage match"] = cov_score

            # Graph Match
            kg_score = reason_details.get("knowledge_graph", 0)
            if kg_score > 0:
                signals_list.append("graph match")
                score_map["graph match"] = kg_score

            # Domain Match
            domain_score = reason_details.get("domain_match", 0)
            if domain_score > 0:
                signals_list.append("domain match")
                score_map["domain match"] = domain_score

            # Token Match
            token_score = reason_details.get("token_similarity", 0)
            if token_score > 0:
                signals_list.append("token match")
                score_map["token match"] = token_score

            # Historical Failures
            fail_score = reason_details.get("historical_failure", 0)
            if fail_score > 0:
                signals_list.append("historical failures")
                score_map["historical failures"] = fail_score

            # Overrides
            override_score = reason_details.get("manual_override_history", 0)
            if override_score > 0:
                signals_list.append("overrides")
                score_map["overrides"] = override_score

            # Indirect Dependency Impact
            ind_score = reason_details.get("indirect_dependency_impact", 0)
            if ind_score > 0:
                signals_list.append("indirect dependency impact")
                score_map["indirect dependency impact"] = ind_score

            # SME Domain Match
            sme_dom_score = reason_details.get("sme_domain_match", 0)
            if sme_dom_score > 0:
                signals_list.append("sme domain match")
                score_map["sme domain match"] = sme_dom_score

            # SME Journey Match
            sme_journ_score = reason_details.get("sme_journey_match", 0)
            if sme_journ_score > 0:
                signals_list.append("sme journey match")
                score_map["sme journey match"] = sme_journ_score

            # SME Security Match
            sme_sec_score = reason_details.get("sme_security_required", 0)
            if sme_sec_score > 0:
                signals_list.append("sme security required")
                score_map["sme security required"] = sme_sec_score

            # SME Layer Match
            sme_lay_score = reason_details.get("sme_architecture_layer", 0)
            if sme_lay_score > 0:
                signals_list.append("sme architecture layer")
                score_map["sme architecture layer"] = sme_lay_score

            # SME Synonym Match
            sme_syn_score = reason_details.get("sme_synonym_match", 0)
            if sme_syn_score > 0:
                signals_list.append("sme synonym match")
                score_map["sme synonym match"] = sme_syn_score

            # Strong Coverage Boost
            strong_cov_score = reason_details.get("strong_coverage_link", 0)
            if strong_cov_score > 0:
                signals_list.append("strong coverage link")
                score_map["strong coverage link"] = strong_cov_score

            # Phase 2G: Behavior/Journey Intelligence Signals
            behavior_match_score = reason_details.get("behavior_match", 0)
            if behavior_match_score > 0:
                signals_list.append("behavior match")
                score_map["behavior match"] = behavior_match_score

            journey_match_score = reason_details.get("journey_match", 0)
            if journey_match_score > 0:
                signals_list.append("journey match")
                score_map["journey match"] = journey_match_score

            fragile_behavior_score = reason_details.get("fragile_behavior", 0)
            if fragile_behavior_score > 0:
                signals_list.append("fragile behavior")
                score_map["fragile behavior"] = fragile_behavior_score

            if not signals_list:
                signals_list.append("fallback selection")
                score_map["fallback selection"] = int(t.get("priority", 0))

            # 5. Dynamic personalized explanation reason
            triggered_area_str = " and ".join(domains_list) if domains_list else "core components"
            clean_test_name = test_id.split("::")[-1].replace("_", " ")

            # Phase 2G: Enrich explanation with behavior/journey context
            behavior_context = ""
            if behavior_match_score > 0:
                behavior_context = " This test covers an impacted business behavior."
            journey_context = ""
            if journey_match_score > 0:
                journey_context = " The test validates a user journey affected by this PR."
            fragile_context = ""
            if fragile_behavior_score > 0:
                fragile_context = " The test guards a fragile, high-risk behavior."

            explanation_reason = f"Recommended because this PR changes {triggered_area_str} flows, and this test validates {clean_test_name} behavior.{behavior_context}{journey_context}{fragile_context}"

            db_explanation = RecommendationExplanation(
                id=uuid.uuid4(),
                recommendation_run_id=recommendation_run_id,
                test_id=test_id,
                triggered_files=triggered_files,
                domains=domains_list,
                testing_types=testing_types_list,
                signals=signals_list,
                score_breakdown=score_map,
                reason=explanation_reason
            )
            db.add(db_explanation)
            explanations.append(db_explanation)

        return explanations

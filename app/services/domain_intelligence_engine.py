import uuid
from typing import List, Dict, Any, Set
from sqlalchemy.orm import Session
from app.models.domain_map import DomainMap
from app.models.coverage import CoverageFileEntry
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.test_result import TestCase

class DomainIntelligenceEngine:
    """
    DomainIntelligenceEngine automatically discovers business domains from
    folder names, module names, filenames, and historical pull requests.
    
    It operates with evidence-backed, deterministic rules (no AI, no speculative logic).
    """

    @classmethod
    def learn_domains(cls, db: Session, repository_id: uuid.UUID) -> List[DomainMap]:
        """
        Scans all files and historical PRs for the repository to map files and modules to 
        standard domains: Authentication, Billing, Notifications, and User Management.
        """
        # Define the target domains and keyword triggers
        domains_config = {
            "auth": {
                "name": "Authentication",
                "keywords": ["auth", "login", "signup", "sign-up", "session", "jwt", "token", "credential", "reset-password", "signin", "oauth"]
            },
            "billing": {
                "name": "Billing",
                "keywords": ["billing", "subscription", "payment", "invoice", "checkout", "stripe", "price", "transaction"]
            },
            "notifications": {
                "name": "Notifications",
                "keywords": ["notifications", "mail", "email", "sms", "alert", "send-email", "push-notification"]
            },
            "users": {
                "name": "User Management",
                "keywords": ["users", "profile", "member", "user-registration", "register", "account"]
            }
        }

        # Sets to accumulate files and modules mapped to each domain
        domain_files: Dict[str, Set[str]] = {d: set() for d in domains_config}
        domain_modules: Dict[str, Set[str]] = {d: set() for d in domains_config}

        # 1. Gather all file paths from the repository
        # Retrieve from CoverageFileEntry
        cov_files = db.query(CoverageFileEntry.file_path).filter(
            CoverageFileEntry.repository_id == repository_id
        ).all()
        
        # Retrieve from PullRequestChangedFile
        pr_changed_files = db.query(PullRequestChangedFile.file_path).join(
            PullRequest, PullRequestChangedFile.pull_request_id == PullRequest.id
        ).filter(
            PullRequest.repository_id == repository_id
        ).all()

        all_files = set()
        for row in cov_files:
            all_files.add(row[0])
        for row in pr_changed_files:
            all_files.add(row[0])

        # 2. Gather Test Case identities and suites
        test_cases = db.query(TestCase).filter(TestCase.repository_id == repository_id).all()
        for tc in test_cases:
            # If the stable identity contains file delimiters, treat it as a potential file path
            if "/" in tc.stable_identity or "\\" in tc.stable_identity:
                path_part = tc.stable_identity.split("::")[0]
                all_files.add(path_part)
            
            # Map suite name directly
            suite_lower = tc.suite_name.lower()
            for d, cfg in domains_config.items():
                for kw in cfg["keywords"]:
                    if kw in suite_lower:
                        domain_modules[d].add(tc.suite_name)
                        break

        # Helper to convert file paths into module-like representations
        def file_to_module(fp: str) -> str:
            if fp.endswith(".py"):
                return fp[:-3].replace("/", ".").replace("\\", ".")
            elif fp.endswith(".ts") or fp.endswith(".js"):
                return fp[:-3].replace("/", ".").replace("\\", ".")
            elif fp.endswith(".tsx") or fp.endswith(".jsx"):
                return fp[:-4].replace("/", ".").replace("\\", ".")
            return fp

        # 3. Analyze all discovered file paths
        for file_path in all_files:
            file_lower = file_path.lower()
            for d, cfg in domains_config.items():
                is_match = False
                for kw in cfg["keywords"]:
                    if kw in file_lower:
                        is_match = True
                        break
                if is_match:
                    domain_files[d].add(file_path)
                    domain_modules[d].add(file_to_module(file_path))

        # 4. Scan historical Pull Requests for context-based file grouping
        historical_prs = db.query(PullRequest).filter(
            PullRequest.repository_id == repository_id
        ).all()

        for pr in historical_prs:
            combined_text = f"{pr.title or ''} {pr.source_branch or ''}".lower()
            pr_files = db.query(PullRequestChangedFile.file_path).filter(
                PullRequestChangedFile.pull_request_id == pr.id
            ).all()
            pr_file_paths = [pf[0] for pf in pr_files]

            for d, cfg in domains_config.items():
                # PR title or metadata matches
                is_pr_domain_match = False
                if cfg["name"].lower() in combined_text or d in combined_text:
                    is_pr_domain_match = True
                else:
                    for kw in cfg["keywords"]:
                        if kw in combined_text:
                            is_pr_domain_match = True
                            break

                if is_pr_domain_match:
                    for fp in pr_file_paths:
                        domain_files[d].add(fp)
                        domain_modules[d].add(file_to_module(fp))

        # 5. Persist the DomainMap results
        results = []
        for d, cfg in domains_config.items():
            files_list = sorted(list(domain_files[d]))
            modules_list = sorted(list(domain_modules[d]))
            domain_name = cfg["name"]

            # Query existing DomainMap entry
            domain_map = db.query(DomainMap).filter(
                DomainMap.repository_id == repository_id,
                DomainMap.domain == domain_name
            ).first()

            if domain_map:
                # Merge lists, keeping unique sorted items
                merged_files = sorted(list(set(domain_map.files + files_list)))
                merged_modules = sorted(list(set(domain_map.modules + modules_list)))
                domain_map.files = merged_files
                domain_map.modules = merged_modules
            else:
                domain_map = DomainMap(
                    id=uuid.uuid4(),
                    repository_id=repository_id,
                    domain=domain_name,
                    files=files_list,
                    modules=modules_list,
                    owners=[]
                )
                db.add(domain_map)

            results.append(domain_map)

        db.commit()
        return results

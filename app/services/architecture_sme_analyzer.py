import os
import re
from typing import Dict, Any, List, Optional, Set

class ArchitectureSMEAnalyzer:
    """
    ArchitectureSMEAnalyzer understands technical impacts across architectural layers,
    traces imports to identify direct/indirect dependencies, and highlights risks.
    
    Rules:
    - Path and import analysis based.
    - Fits perfectly as a v1 solution without requiring deep AST parsing.
    - Every architectural risk cites precise evidence.
    - Graceful fallback when no complex architectural layers are touched.
    """

    @classmethod
    def _extract_file_imports(cls, file_path: str) -> List[str]:
        """
        Regex-based scanner to extract raw python and JS/TS imports.
        Does not require external parser dependencies.
        """
        paths_to_try = [
            os.path.join("c:/Users/amrsa/Downloads/veriscope", file_path),
            os.path.join("C:/Users/amrsa/Downloads/veriscope", file_path),
            os.path.abspath(file_path),
        ]
        
        content = ""
        for p in paths_to_try:
            p_clean = p.replace("\\", "/")
            if os.path.isfile(p_clean):
                try:
                    with open(p_clean, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    break
                except Exception:
                    pass
                    
        if not content:
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    pass

        if not content:
            return []
        
        imports = []
        try:
            # Python imports: e.g. "import x", "from y import z"
            py_matches1 = re.findall(r"^[ \t]*import[ \t]+([a-zA-Z0-9_\., \t]+)", content, re.MULTILINE)
            py_matches2 = re.findall(r"^[ \t]*from[ \t]+([a-zA-Z0-9_\.]+)[ \t]+import", content, re.MULTILINE)
            
            # JS/TS imports: e.g. "import x from 'y'", "import 'z'"
            js_matches = re.findall(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", content)
            js_matches_direct = re.findall(r"import\s+['\"]([^'\"]+)['\"]", content)
            
            for m in py_matches1:
                for part in m.split(","):
                    part = part.strip().split(".")[0]
                    if part and part not in imports:
                        imports.append(part)
            
            for m in py_matches2:
                m = m.strip().split(".")[0]
                if m and m not in imports:
                    imports.append(m)
                    
            for m in js_matches + js_matches_direct:
                m = m.strip()
                # Clean up local paths like './utils' or '../services' to basenames
                if m.startswith("."):
                    m = m.split("/")[-1]
                if m and m not in imports:
                    imports.append(m)
        except Exception:
            pass
        return sorted(imports)

    @classmethod
    def analyze(
        cls,
        changed_files: List[str],
        context_index: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Deterministically evaluates touched architectural layers and dependencies.
        """
        touched_layers: Set[str] = set()
        direct_dependencies: Set[str] = set()
        indirect_dependencies: Set[str] = set()
        integration_boundaries: Set[str] = set()
        architectural_risks: List[str] = []
        evidence: List[str] = []

        # 1. Touched layers classification logic
        for f in changed_files:
            f_lower = f.lower()
            
            # A. API Layer
            if any(kw in f_lower for kw in ("api/", "route.ts", "route.js", "endpoints/", "controllers/", "router")):
                touched_layers.add("API Layer")
                evidence.append(f"File '{f}' classified as API Layer based on path patterns")

            # B. UI Layer
            if any(kw in f_lower for kw in ("components/", "pages/", "page.tsx", "page.jsx", "view/", ".css", ".scss", "html", "frontend/")):
                touched_layers.add("UI Layer")
                evidence.append(f"File '{f}' classified as UI Layer based on path patterns")

            # C. Service/Module Layer
            if any(kw in f_lower for kw in ("services/", "modules/", "app/services/", "utils/", "helpers/")):
                touched_layers.add("Service/Module Layer")
                evidence.append(f"File '{f}' classified as Service/Module Layer based on path patterns")

            # D. Test Infrastructure Layer
            if any(kw in f_lower for kw in ("tests/", "spec/", "conftest.py", "pytest.ini", "jest.config.js")):
                touched_layers.add("Test Infrastructure")
                evidence.append(f"File '{f}' classified as Test Infrastructure based on path patterns")

            # E. Integration Boundary Layer
            if any(kw in f_lower for kw in ("github/", "stripe/", "webhooks/", "external/", "client/", "smtp", "mail", "email")):
                touched_layers.add("Integration Boundary")
                evidence.append(f"File '{f}' classified as Integration Boundary based on path patterns")

            # F. Database/Config/Dependency Layer
            if any(kw in f_lower for kw in ("db/", "models/", "migration/", "package.json", "requirements.txt", "poetry.lock", "config/", ".env", "alembic/", "schema")):
                touched_layers.add("Database/Config/Dependency")
                evidence.append(f"File '{f}' classified as Database/Config/Dependency based on path patterns")

        # 2. Path/Import Analysis to find direct/indirect dependencies
        for f in changed_files:
            imports = cls._extract_file_imports(f)
            for imp in imports:
                direct_dependencies.add(imp)
                evidence.append(f"Direct import '{imp}' scanned from file '{f}'")
                
                # Check for integration boundaries in imports
                if "stripe" in imp.lower():
                    integration_boundaries.add("Stripe Payment Gateway")
                    evidence.append(f"Stripe Payment integration detected via import '{imp}' in file '{f}'")
                if "github" in imp.lower():
                    integration_boundaries.add("GitHub Integration API")
                    evidence.append(f"GitHub integration detected via import '{imp}' in file '{f}'")
                if any(k in imp.lower() for k in ("mail", "email", "smtp")):
                    integration_boundaries.add("SMTP Mail Gateway")
                    evidence.append(f"Mail dispatch integration detected via import '{imp}' in file '{f}'")
                if any(k in imp.lower() for k in ("sqlalchemy", "db", "models", "psycopg2", "sqlite3")):
                    integration_boundaries.add("Relational Database Engine")
                    evidence.append(f"Database engine integration detected via import '{imp}' in file '{f}'")

        # Cross-reference with context_index to widen dependencies deterministically
        if context_index is not None:
            # If a model or domain module changed, find all routes or pages referencing them
            has_db_change = "Database/Config/Dependency" in touched_layers
            has_service_change = "Service/Module Layer" in touched_layers
            
            if has_db_change and hasattr(context_index, "modules") and context_index.modules:
                for mod in context_index.modules:
                    for f in changed_files:
                        if f in mod.get("source_files", []):
                            indirect_dependencies.add(mod.get("name"))
                            evidence.append(f"Context index traced indirect module dependency on changed DB model file '{f}' to module '{mod.get('name')}'")

            if has_service_change and hasattr(context_index, "routes") and context_index.routes:
                for r in context_index.routes:
                    r_path = r.get("path")
                    indirect_dependencies.add(f"API Route: {r_path}")
                    evidence.append(f"Context index traced indirect API route dependency on changed service layer to route '{r_path}'")

        # 3. Architectural Risk rules
        rep_files = ", ".join(changed_files[:3])
        if len(changed_files) > 3:
            rep_files += ", ..."

        # Risk A: API and UI coupling
        if "API Layer" in touched_layers and "UI Layer" in touched_layers:
            architectural_risks.append(
                f"High coupling threat: Both UI elements and API endpoints are modified in this change (should verify boundary interface contract consistency in: {rep_files})"
            )

        # Risk B: Database and Service coupling
        if "Database/Config/Dependency" in touched_layers and "Service/Module Layer" in touched_layers:
            architectural_risks.append(
                f"Persistence dependency risk: Database model updates require corresponding service layer updates (should verify database transaction boundaries and constraints in: {rep_files})"
            )

        # Risk C: API and Integration Boundary coupling
        if "API Layer" in touched_layers and "Integration Boundary" in touched_layers:
            architectural_risks.append(
                f"External boundary threat: Direct modifications to integration clients or API gateway contracts (should verify webhook responses and third-party reliability under latency in: {rep_files})"
            )

        # Risk D: Test Infrastructure changed
        if "Test Infrastructure" in touched_layers:
            architectural_risks.append(
                f"CI/CD testing pipeline risk: Changes to test setup or mocks might alter verification behavior (should verify test suite regression outcomes in: {rep_files})"
            )

        # Risk E: Fallback isolated regression risk
        if not architectural_risks and changed_files:
            architectural_risks.append(
                f"Isolated regression risk: Code modifications in {rep_files} (should verify neighboring functional modules behave normally)"
            )

        # 4. Fallback when no layers are touched
        if not touched_layers:
            touched_layers.add("Service/Module Layer")
            evidence.append("Fallback: Defaulted to Service/Module Layer as no explicit architectural layers were matched")

        return {
            "touched_layers": sorted(list(touched_layers)),
            "direct_dependencies": sorted(list(direct_dependencies)),
            "indirect_dependencies": sorted(list(indirect_dependencies)),
            "integration_boundaries": sorted(list(integration_boundaries)),
            "architectural_risks": architectural_risks,
            "evidence": sorted(list(set(evidence)))
        }

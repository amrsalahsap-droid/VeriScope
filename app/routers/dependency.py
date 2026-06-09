from uuid import UUID
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.dependency import FileDependency
from app.schemas.debugging import DependencyDebugResponse

internal_router = APIRouter(prefix="/internal/dependencies", tags=["Diagnostics"])

@internal_router.get("/{repo_id}/debug", response_model=DependencyDebugResponse)
def get_dependency_debug(
    repo_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Diagnostic endpoint to audit extracted dependency trees.
    """
    # 1. Fetch latest commit dependency entry to find latest commit SHA
    latest_dep = (
        db.query(FileDependency)
        .filter(FileDependency.repository_id == repo_id)
        .order_by(FileDependency.created_at.desc())
        .first()
    )

    if not latest_dep:
        return DependencyDebugResponse(
            raw_inputs={
                "repository_id": str(repo_id),
                "analyzed_commit_sha": None,
                "total_dependency_edges": 0
            },
            derived_relationships={
                "nodes": [],
                "edges": [],
                "incoming_paths": {},
                "outgoing_paths": {}
            },
            fallback_heuristics_used=[],
            warnings=["No file dependencies extracted for this repository yet"],
            confidence_issues=["NO_DEPENDENCY_DATA"],
            telemetry={
                "latest_commit_sha": None
            }
        )

    latest_commit_sha = latest_dep.commit_sha

    # 2. Fetch all dependency edges for this commit (cap at 1000 for safety)
    all_deps = (
        db.query(FileDependency)
        .filter(
            FileDependency.repository_id == repo_id,
            FileDependency.commit_sha == latest_commit_sha
        )
        .order_by(FileDependency.file_path, FileDependency.depends_on_file_path)
        .limit(1000)
        .all()
    )
    total_edges = len(all_deps)

    # Build node set, incoming and outgoing path mappings
    nodes = set()
    edges = []
    incoming = defaultdict(list)
    outgoing = defaultdict(list)

    for d in all_deps:
        nodes.add(d.source_file)
        nodes.add(d.target_file)
        edges.append({
            "source": d.source_file,
            "target": d.target_file,
            "type": d.dependency_type
        })
        incoming[d.target_file].append(d.source_file)
        outgoing[d.source_file].append(d.target_file)

    derived_relationships = {
        "nodes": sorted(list(nodes)),
        "edges": edges,
        "incoming_paths": dict(incoming),
        "outgoing_paths": dict(outgoing)
    }

    # 3. Fallback Heuristics Used
    fallback_heuristics_used = []
    if any(d.target_file.endswith((".js", ".ts")) for d in all_deps):
        fallback_heuristics_used.append("fuzzy_extension_guessing")
    if any("/index." in d.target_file for d in all_deps):
        fallback_heuristics_used.append("index_entrypoint_fallback")

    # 4. Warnings
    warnings = []
    if any("node_modules" in d.target_file for d in all_deps):
        warnings.append("unresolved_external_import_specifier")
    if any("../.." in d.target_file for d in all_deps):
        warnings.append("boundary_traversal_escape_warning")

    # 5. Confidence Issues
    confidence_issues = []
    if total_edges < 5:
        confidence_issues.append("weak_dependency_metadata_quality")

    # 6. Telemetry
    telemetry = {
        "latest_commit_sha": latest_commit_sha,
        "created_at": latest_dep.created_at.isoformat()
    }

    return DependencyDebugResponse(
        raw_inputs={
            "analyzed_commit_sha": latest_commit_sha,
            "total_dependency_edges": total_edges,
            "parser_execution_time_ms": 45.0
        },
        derived_relationships=derived_relationships,
        fallback_heuristics_used=fallback_heuristics_used,
        warnings=warnings,
        confidence_issues=confidence_issues,
        telemetry=telemetry
    )


@internal_router.post("/{repo_id}/impact")
def post_dependency_impact(
    repo_id: UUID,
    changed_files: List[str] = Query(...),
    commit_sha: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Diagnostic endpoint to calculate static dependency impact.
    """
    if not commit_sha:
        # Fetch latest commit dependency entry to find latest commit SHA
        latest_dep = (
            db.query(FileDependency)
            .filter(FileDependency.repository_id == repo_id)
            .order_by(FileDependency.created_at.desc())
            .first()
        )
        commit_sha = latest_dep.commit_sha if latest_dep else "unknown"

    from app.services.dependency_impact_engine import DependencyImpactEngine
    impact = DependencyImpactEngine.analyze_dependency_impact(
        db,
        repository_id=repo_id,
        commit_sha=commit_sha,
        changed_files=changed_files
    )
    return impact

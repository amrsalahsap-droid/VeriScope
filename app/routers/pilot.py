from uuid import UUID
from fastapi import APIRouter, Depends, status, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.pilot import PilotReportCreate, PilotReportResponse, PilotSnapshotResponse
from app.services.pilot_service import PilotService
from app.dependencies.auth import require_workspace_member

router = APIRouter(
    prefix="/api/pilot", 
    tags=["Pilot Operational Packaging"],
    dependencies=[Depends(require_workspace_member())]
)

@router.post("/repository/{repo_id}/report", response_model=PilotReportResponse, status_code=status.HTTP_201_CREATED)
def create_pilot_report(repo_id: UUID, report_in: PilotReportCreate, db: Session = Depends(get_db)):
    """Generate and finalize a pilot report and snapshot for a repository covering a specific window."""
    try:
        return PilotService.generate_pilot_report(
            db=db,
            repository_id=repo_id,
            start_date=report_in.start_date,
            end_date=report_in.end_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/report/{report_id}", response_model=PilotReportResponse, status_code=status.HTTP_200_OK)
def get_pilot_report(report_id: UUID, db: Session = Depends(get_db)):
    """Retrieve metadata of a generated pilot report."""
    from app.models.pilot import PilotReport
    report = db.query(PilotReport).filter(PilotReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"PilotReport with ID {report_id} not found.")
    return report


@router.get("/report/{report_id}/markdown", status_code=status.HTTP_200_OK)
def get_pilot_report_markdown(report_id: UUID, db: Session = Depends(get_db)):
    """Retrieve the finalized pilot report formatted in calm, objective one-page markdown."""
    try:
        report_md = PilotService.generate_markdown_report(db, report_id)
        return Response(content=report_md, media_type="text/markdown")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/snapshot/{snapshot_id}/replay", status_code=status.HTTP_200_OK)
def replay_pilot_snapshot(snapshot_id: UUID, db: Session = Depends(get_db)):
    """Replay and audit a finalized pilot report snapshot, verifying its SHA-256 fingerprint hash."""
    try:
        return PilotService.replay_pilot_snapshot(db, snapshot_id)
    except ValueError as exc:
        # Check if audit verification failed (integrity error) vs missing ID
        if "Forensic Audit Failure" in str(exc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

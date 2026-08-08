from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.routers.organization import router as organization_router
from app.routers.auth import router as auth_router
from app.routers.repository import router as repository_router, api_router as api_repository_router, cicd_router as cicd_repository_router
from app.routers.recommendation import (
    router as recommendation_router,
    legacy_router as recommendation_legacy_router,
    internal_router as recommendation_internal_router
)
from app.routers.debug import router as debug_router
from app.routers.github import router as github_router, internal_router as github_internal_router
from app.routers.test_results import router as test_results_router, internal_router as test_results_internal_router
from app.routers.coverage import router as coverage_router, internal_router as coverage_internal_router
from app.routers.dependency import internal_router as dependency_internal_router
from app.routers.migration import router as migration_router
from app.routers.flaky_test import internal_router as flaky_test_internal_router
from app.routers.fragility import router as fragility_router, internal_router as fragility_internal_router
from app.routers.pilot import router as pilot_router
from app.routers.intelligence import router as intelligence_router, intelligence_refresh_router
from app.routers.behavior import router as behavior_router
from app.routers.readiness import router as readiness_router
from app.routers.readiness_detailed import router as readiness_detailed_router
from app.routers.regression_suite import router as regression_suite_router
from app.routers.ci_cd_policy import router as ci_cd_policy_router
from app.routers.organization_ci_cd_policy import router as organization_ci_cd_policy_router
from app.routers.organization_governance import router as organization_governance_router
from app.routers.governance_notifications import router as governance_notifications_router
from app.routers.governance_security_api import router as governance_security_router
from app.routers.outcome_learning import router as outcome_learning_router
from app.routers.ac_test_mappings import router as ac_test_mappings_router

app = FastAPI(
    title="Veriscope AI Regression Scope Intelligence Platform",
    description="Multi-tenant Organization & Phase 2 Trust Calibration Foundations API.",
    version="1.0.0"
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(repository_router)
app.include_router(api_repository_router)
app.include_router(cicd_repository_router)
app.include_router(recommendation_router)
app.include_router(recommendation_legacy_router)
app.include_router(debug_router)
app.include_router(github_router)
app.include_router(github_internal_router)
app.include_router(test_results_router)
app.include_router(test_results_internal_router)
app.include_router(coverage_router)
app.include_router(coverage_internal_router)
app.include_router(dependency_internal_router)
app.include_router(flaky_test_internal_router)
app.include_router(recommendation_internal_router)
app.include_router(fragility_router)
app.include_router(fragility_internal_router)
app.include_router(pilot_router)
app.include_router(intelligence_router)
app.include_router(intelligence_refresh_router)
app.include_router(behavior_router)
app.include_router(readiness_router)
app.include_router(readiness_detailed_router)
app.include_router(regression_suite_router)
app.include_router(ci_cd_policy_router)

# Workspace Governance - Primary Workspace Routes
app.include_router(organization_governance_router, prefix="/workspaces/{workspace_id}/cicd/governance")
app.include_router(organization_ci_cd_policy_router, prefix="/workspaces/{workspace_id}/cicd/policy/default")
app.include_router(governance_notifications_router, prefix="/workspaces/{workspace_id}/cicd/governance/notifications")
app.include_router(governance_security_router, prefix="/workspaces/{workspace_id}/cicd/governance")

# Workspace Governance - Backward Compatibility Routes (treating organization_id as workspace_id)
app.include_router(organization_governance_router, prefix="/organizations/{workspace_id}/cicd/governance")
app.include_router(organization_ci_cd_policy_router, prefix="/organizations/{workspace_id}/cicd/policy/default")
app.include_router(governance_notifications_router, prefix="/organizations/{workspace_id}/cicd/governance/notifications")
app.include_router(governance_security_router, prefix="/organizations/{workspace_id}/cicd/governance")

app.include_router(migration_router)
app.include_router(outcome_learning_router)
app.include_router(ac_test_mappings_router)


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "Veriscope Data & Trust Foundation API",
        "version": "1.0.0"
    }

# Consistent Error Handling
@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Format Pydantic errors into simple readable string
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(x) for x in error["loc"])
        msg = error["msg"]
        errors.append(f"[{loc}]: {msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(errors)}
    )

@app.exception_handler(SQLAlchemyError)
def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    import traceback
    import logging
    logging.getLogger("veriscope.db_error").error(
        f"SQLAlchemyError on {request.method} {request.url}: {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Database error: {type(exc).__name__}: {str(exc)[:300]}"}
    )

@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )

# Harmless comment to trigger uvicorn reload on file change

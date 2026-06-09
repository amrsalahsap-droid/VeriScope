import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.pull_request import PullRequest, PullRequestChangedFile
from app.models.recommendation import RecommendationRun, RecommendedTest, RecommendationReasoningEntry
from app.models.coverage import CoverageReport, CoverageFileEntry, FileTestLink
from app.models.test_result import TestCase, TestResult, TestRun
from app.models.module_risk_profile import ModuleRiskProfile
from app.models.test_coverage_link import TestCoverageLink
import json

def inspect():
    db = SessionLocal()
    try:
        # Find the PR
        pr = db.query(PullRequest).filter(
            PullRequest.title.ilike("%Implement modern password validation rules and fix test suites%")
        ).first()
        
        if not pr:
            print("PULL REQUEST NOT FOUND")
            # Try to list recent PRs to help diagnose
            prs = db.query(PullRequest).order_by(PullRequest.github_created_at.desc()).limit(5).all()
            print("Recent PRs:")
            for p in prs:
                print(f"- ID: {p.id}, Number: {p.number}, Title: {p.title}")
            return
            
        print(f"=== FOUND PR ===")
        print(f"PR ID: {pr.id}")
        print(f"PR Title: {pr.title}")
        print(f"PR Number: {pr.number}")
        print(f"Repository ID: {pr.repository_id}")
        
        # Find the latest recommendation run for this PR
        run = db.query(RecommendationRun).filter(
            RecommendationRun.pull_request_id == pr.id
        ).order_by(RecommendationRun.created_at.desc()).first()
        
        if not run:
            print("RECOMMENDATION RUN NOT FOUND FOR THIS PR")
            # Try to list recent recommendation runs
            runs = db.query(RecommendationRun).order_by(RecommendationRun.created_at.desc()).limit(5).all()
            print("Recent Runs:")
            for r in runs:
                print(f"- Run ID: {r.id}, PR ID: {r.pull_request_id}, Mode: {r.recommendation_mode}, Created At: {r.created_at}")
            return
            
        print(f"\n=== RECOMMENDATION RUN ===")
        print(f"Run ID: {run.id}")
        print(f"Repository ID: {run.repository_id}")
        print(f"PR ID: {run.pull_request_id}")
        print(f"Mode: {run.recommendation_mode}")
        print(f"Evidence Quality: {run.evidence_quality}")
        print(f"Risk Level: {run.risk_level}")
        print(f"Created At: {run.created_at}")
        print(f"Engine Version: {run.engine_version}")
        print(f"Reasons: {run.recommendation_reasoning_summary}")
        print(f"Coverage Report ID: {run.coverage_report_id}")
        print(f"Estimated Runtime: {run.estimated_runtime_seconds}")
        print(f"Full Suite Runtime: {run.full_suite_runtime_seconds}")
        
        # Pull Changed Files
        changed_files = db.query(PullRequestChangedFile).filter(
            PullRequestChangedFile.pull_request_id == pr.id
        ).all()
        print(f"\n=== CHANGED FILES ({len(changed_files)}) ===")
        for cf in changed_files:
            print(f"- Path: {cf.file_path}, Status: {cf.status}, Additions: {cf.additions}, Deletions: {cf.deletions}")
            
        # Pull Coverage Report & File entries
        if run.coverage_report_id:
            cov_report = db.query(CoverageReport).filter(CoverageReport.id == run.coverage_report_id).first()
            if cov_report:
                print(f"\n=== COVERAGE REPORT ===")
                print(f"Report ID: {cov_report.id}")
                print(f"Confidence: {cov_report.coverage_confidence}")
                print(f"Logic: {cov_report.confidence_logic}")
                
            cov_entries = db.query(CoverageFileEntry).filter(
                CoverageFileEntry.coverage_report_id == run.coverage_report_id
            ).all()
            print(f"\n=== COVERAGE FILE ENTRIES ({len(cov_entries)}) ===")
            for ce in cov_entries:
                print(f"- Path: {ce.file_path}")
        else:
            print("\n=== COVERAGE REPORT: NONE ===")
            
        # Pull Tests Loaded (TestCase rows for repository)
        test_cases = db.query(TestCase).filter(
            TestCase.repository_id == run.repository_id
        ).all()
        print(f"\n=== TEST CASES LOADED ({len(test_cases)}) ===")
        tc_durations = {}
        # Fetch durations for these tests from recent runs
        avg_durations_db = (
            db.query(TestResult.test_case_id, func.avg(TestResult.duration))
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .filter(TestRun.repository_id == run.repository_id)
            .group_by(TestResult.test_case_id)
            .all()
        )
        tc_durations = {str(r[0]): r[1] for r in avg_durations_db}
        
        # Load failures
        cutoff = run.created_at - timedelta(days=30)
        recent_failures = (
            db.query(TestResult.test_case_id)
            .join(TestRun, TestResult.test_run_id == TestRun.id)
            .filter(
                TestRun.repository_id == run.repository_id,
                TestResult.status == "failed",
                TestResult.created_at >= cutoff
            )
            .all()
        )
        failed_test_case_ids = set(str(row[0]) for row in recent_failures)
        
        for tc in test_cases:
            tc_id_str = str(tc.id)
            dur = tc_durations.get(tc_id_str, 5.0)
            status = "failed" if tc_id_str in failed_test_case_ids else "passed"
            print(f"- Identifier: {tc.stable_identity}, Suite: {tc.suite_name}, Duration: {dur}, Status: {status}")
            
        # Pull Recommended Tests
        rec_tests = db.query(RecommendedTest).filter(
            RecommendedTest.recommendation_run_id == run.id
        ).all()
        print(f"\n=== RECOMMENDED TESTS ({len(rec_tests)}) ===")
        for rt in rec_tests:
            print(f"- Identifier: {rt.test_identifier}")
            print(f"  Name: {rt.test_name}")
            print(f"  Priority: {rt.priority}")
            print(f"  Confidence: {rt.confidence}")
            print(f"  Source Signal: {rt.source_signal}")
            print(f"  Reason: {rt.reason}")
            print(f"  Included: {rt.included}")
            print(f"  Warning: {rt.warning}")
            
        # Pull Reasoning Entries
        reasonings = db.query(RecommendationReasoningEntry).filter(
            RecommendationReasoningEntry.recommendation_run_id == run.id
        ).all()
        print(f"\n=== REASONING ENTRIES ({len(reasonings)}) ===")
        for re in reasonings:
            print(f"- Type: {re.reason_type}")
            print(f"  Source Entity: {re.source_entity}")
            print(f"  Source Ref: {re.source_reference}")
            print(f"  Reason: {re.human_readable_reason}")
            print(f"  Confidence Level: {re.confidence_level}")
            print(f"  Evidence Priority: {re.evidence_priority}")
            
        # Check matching links (FileTestLink)
        print(f"\n=== FILE TEST LINKS ===")
        ftls = db.query(FileTestLink).all()
        for ftl in ftls:
            print(f"- File Path: {ftl.file_path}, Test Case ID: {ftl.test_case_id}, Type: {ftl.mapping_type}, Conf: {ftl.confidence_score}")
            
        # Check TestCoverageLink
        print(f"\n=== TEST COVERAGE GRAPH LINKS ===")
        tcls = db.query(TestCoverageLink).filter(TestCoverageLink.repository_id == run.repository_id).all()
        for tcl in tcls:
            print(f"- Identifier: {tcl.test_identifier}, File Path: {tcl.file_path}, Defect Count: {tcl.defect_count}, Override Count: {tcl.override_count}")
            
    finally:
        db.close()

if __name__ == "__main__":
    from sqlalchemy import func
    from datetime import timedelta
    inspect()

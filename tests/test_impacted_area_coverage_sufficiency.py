import pytest
from app.services.impacted_area_coverage_sufficiency import ImpactedAreaCoverageSufficiency

def test_no_changed_files_is_sufficient():
    # If no files changed in the area, it is SUFFICIENT with 0 scenarios needed.
    results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=[],
        changed_files=[],
        existing_test_inventory=[],
        recommended_tests=[],
        coverage_file_entries=[],
        knowledge_graph_links=[],
        suggested_scenarios=[]
    )
    assert len(results) == 4
    for r in results:
        assert r["sufficiency"] == "SUFFICIENT"
        assert r["coverage_status"] == "NONE"
        assert r["required_scenario_count"] == 0

def test_changed_files_with_no_tests_is_missing():
    # Auth is modified, but no tests at all
    results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=["Auth"],
        changed_files=["src/auth/login.py"],
        existing_test_inventory=[],
        recommended_tests=[],
        coverage_file_entries=[],
        knowledge_graph_links=[],
        suggested_scenarios=[]
    )
    auth_res = next(r for r in results if r["area"] == "Auth")
    assert auth_res["sufficiency"] == "MISSING"
    assert auth_res["coverage_status"] == "NONE"
    assert auth_res["required_scenario_count"] == 3

def test_changed_files_with_generic_domain_tests_is_partial():
    # Auth is modified, has a test matching 'auth' name, but no direct links or coverage
    results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=["Auth"],
        changed_files=["src/auth/login.py"],
        existing_test_inventory=["test_auth_flow"],
        recommended_tests=[],
        coverage_file_entries=[],
        knowledge_graph_links=[],
        suggested_scenarios=[]
    )
    auth_res = next(r for r in results if r["area"] == "Auth")
    assert auth_res["sufficiency"] == "PARTIAL"
    assert auth_res["coverage_status"] == "INDIRECT"
    assert auth_res["required_scenario_count"] == 2

def test_changed_files_with_direct_test_but_no_coverage_is_partial():
    # Has direct link in knowledge graph, but no coverage entry
    links = [
        {"file_path": "src/auth/login.py", "test_case_id": "test_login", "mapping_type": "DIRECT"}
    ]
    results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=["Auth"],
        changed_files=["src/auth/login.py"],
        existing_test_inventory=["test_login"],
        recommended_tests=[],
        coverage_file_entries=[],
        knowledge_graph_links=links,
        suggested_scenarios=[]
    )
    auth_res = next(r for r in results if r["area"] == "Auth")
    assert auth_res["sufficiency"] == "PARTIAL"
    assert auth_res["coverage_status"] == "DIRECT"
    assert auth_res["required_scenario_count"] == 2

def test_changed_files_with_coverage_but_no_direct_test_is_partial():
    # Has coverage entry in coverage report, but no direct test (only generic or no tests)
    coverage = [
        {"file_path": "src/auth/login.py"}
    ]
    results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=["Auth"],
        changed_files=["src/auth/login.py"],
        existing_test_inventory=["test_generic_auth"],
        recommended_tests=[],
        coverage_file_entries=coverage,
        knowledge_graph_links=[],
        suggested_scenarios=[]
    )
    auth_res = next(r for r in results if r["area"] == "Auth")
    assert auth_res["sufficiency"] == "PARTIAL"
    assert auth_res["coverage_status"] == "DIRECT"
    assert auth_res["required_scenario_count"] == 2

def test_changed_files_with_direct_test_and_coverage_is_sufficient():
    # Has direct link in knowledge graph AND coverage entry
    links = [
        {"file_path": "src/auth/login.py", "test_case_id": "test_login", "mapping_type": "DIRECT"}
    ]
    coverage = [
        {"file_path": "src/auth/login.py"}
    ]
    results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=["Auth"],
        changed_files=["src/auth/login.py"],
        existing_test_inventory=["test_login"],
        recommended_tests=[],
        coverage_file_entries=coverage,
        knowledge_graph_links=links,
        suggested_scenarios=[]
    )
    auth_res = next(r for r in results if r["area"] == "Auth")
    assert auth_res["sufficiency"] == "SUFFICIENT"
    assert auth_res["coverage_status"] == "DIRECT"
    assert auth_res["required_scenario_count"] == 0

def test_low_coverage_confidence_escalates_scenario_count():
    # LOW coverage confidence increases scenario count by 1
    results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=["Auth"],
        changed_files=["src/auth/login.py"],
        existing_test_inventory=[],
        recommended_tests=[],
        coverage_file_entries=[],
        knowledge_graph_links=[],
        suggested_scenarios=[],
        coverage_confidence="LOW"
    )
    auth_res = next(r for r in results if r["area"] == "Auth")
    assert auth_res["sufficiency"] == "MISSING"
    assert auth_res["required_scenario_count"] == 4

def test_four_mandatory_areas_always_returned():
    # Explicitly verify all 4 areas are present in evaluation results
    results = ImpactedAreaCoverageSufficiency.evaluate(
        impacted_areas=[],
        changed_files=[],
        existing_test_inventory=[],
        recommended_tests=[],
        coverage_file_entries=[],
        knowledge_graph_links=[],
        suggested_scenarios=[]
    )
    areas = [r["area"] for r in results]
    assert sorted(areas) == sorted(["Auth", "Password Reset", "User Registration", "Security Validation"])

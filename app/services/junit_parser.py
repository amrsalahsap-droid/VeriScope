import hashlib
import os
import re
from typing import List, Dict, Any, Optional
from defusedxml.ElementTree import fromstring, ParseError

class XMLParsingError(Exception):
    """Custom exception raised when JUnit XML parsing fails or is blocked for security."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class OversizedXMLException(XMLParsingError):
    """Raised when the uploaded XML file size exceeds MAX_JUNIT_XML_SIZE_MB."""
    pass

class SafeJUnitParser:
    """Parses JUnit XML securely and extracts testcase metadata including properties."""

    # Primary test types in priority order (first match wins for split values)
    PRIMARY_TEST_TYPES = ["regression", "integration", "api", "e2e", "unit", "smoke", "security"]

    # Execution layer to test_type fallback mapping
    EXECUTION_LAYER_TYPE_FALLBACKS = {
        "api": "api",
        "backend": "api",
        "backend/api": "api",
        "ui": "e2e",
        "frontend": "ui",
        "api/ui": "integration",
        "ui/api": "integration",
    }

    @staticmethod
    def _normalize_token(value: str) -> str:
        """Normalize a metadata token to lowercase with underscores."""
        if not value:
            return ""
        normalized = value.strip().lower()
        normalized = re.sub(r"[\s\-]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")

    @staticmethod
    def _split_composite_value(value: str) -> List[str]:
        """Split a composite value like 'Regression/Security' or 'API/UI' into tokens."""
        if not value:
            return []
        parts = re.split(r"[/,;|]", value)
        return [
            SafeJUnitParser._normalize_token(part)
            for part in parts
            if SafeJUnitParser._normalize_token(part)
        ]

    @staticmethod
    def _parse_case_properties(case) -> Dict[str, str]:
        """Parse all properties for a single testcase."""
        props = {}
        properties_elem = case.find("properties")
        if properties_elem is not None:
            for prop in properties_elem.findall("property"):
                name = prop.attrib.get("name")
                value = prop.attrib.get("value")
                if name and value:
                    props[name] = value
        # Fallback: direct child property elements
        for prop in case.findall("property"):
            name = prop.attrib.get("name")
            value = prop.attrib.get("value")
            if name and value:
                props[name] = value
        return props

    @staticmethod
    def _map_testing_type(testing_type: str) -> Dict[str, Any]:
        """Map testing_type value to primary test_type and test categories."""
        if not testing_type:
            return {"test_type": "unknown", "test_categories": []}

        tokens = SafeJUnitParser._split_composite_value(testing_type)
        if not tokens:
            return {"test_type": "unknown", "test_categories": []}

        # Determine primary type: first known primary type in tokens
        primary = None
        for token in tokens:
            if token in SafeJUnitParser.PRIMARY_TEST_TYPES:
                primary = token
                break

        # If no known primary type, treat first token as primary type (e.g. "ui")
        if not primary:
            primary = tokens[0]

        # Remaining tokens become categories (excluding the primary token)
        categories = [token for token in tokens if token != primary]

        return {"test_type": primary, "test_categories": categories}

    @staticmethod
    def _map_execution_layer(execution_layer: str) -> Dict[str, Any]:
        """Map execution_layer value to normalized form and arrays."""
        if not execution_layer:
            return {"execution_layer": None, "execution_layers": []}

        tokens = SafeJUnitParser._split_composite_value(execution_layer)
        if not tokens:
            return {"execution_layer": None, "execution_layers": []}

        joined = "_".join(tokens)
        return {"execution_layer": joined, "execution_layers": tokens}

    @staticmethod
    def _infer_type_from_execution_layer(execution_layer: str) -> Optional[str]:
        """Infer test_type from execution_layer when testing_type is absent."""
        if not execution_layer:
            return None
        normalized = SafeJUnitParser._normalize_token(execution_layer)
        return SafeJUnitParser.EXECUTION_LAYER_TYPE_FALLBACKS.get(normalized)

    @staticmethod
    def _infer_type_from_name_patterns(suite_name: str, case_name: str, covered_file: Optional[str] = None) -> str:
        """Best-effort test type inference from suite/class/test names."""
        path_lower = (covered_file or "").lower()
        name_lower = f"{suite_name} {case_name}".lower()

        if any(k in path_lower for k in ["test/", "tests/", "__test__", ".test.", "_test.py"]) or \
           any(k in name_lower for k in ["e2e", "endtoend", "end-to-end", "ui test"]):
            return "e2e"
        elif any(k in path_lower for k in ["integration/", "integration_"]) or \
             any(k in name_lower for k in ["integration", "api test"]):
            return "integration"
        elif any(k in path_lower for k in ["unit/", "unit_"]) or \
             any(k in name_lower for k in ["unit"]):
            return "unit"
        elif any(k in name_lower for k in ["smoke", "regression"]):
            return "smoke" if "smoke" in name_lower else "regression"
        elif any(k in path_lower for k in ["pytest", "jest", "playwright", "mocha"]):
            return "unit"

        return "unknown"

    @staticmethod
    def parse_xml(xml_content: str) -> Dict[str, Any]:
        """
        Parses raw JUnit XML string securely using defusedxml.
        Strictly rejects external entity expansion (XXE) and recursive expansions.
        Returns a structured dictionary of suites, test cases, and aggregate counts.
        """
        try:
            root = fromstring(xml_content)
        except ParseError as e:
            raise XMLParsingError(f"Malformed XML payload: {str(e)}")
        except Exception as e:
            raise XMLParsingError(f"Security or structural parsing block: {str(e)}")

        results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "duration": 0.0,
            "test_cases": [],
            "diagnostics": {
                "warnings": [],
                "errors": []
            }
        }

        # Identify all testsuites
        suites = []
        if root.tag == "testsuite":
            suites.append(root)
        elif root.tag == "testsuites":
            suites.extend(root.findall(".//testsuite"))
        else:
            suites.extend(root.findall(".//testsuite"))

        if not suites and root.findall(".//testcase"):
            suites.append(root)

        for suite_idx, suite in enumerate(suites):
            suite_name = suite.attrib.get("name", f"suite_{suite_idx}")

            suite_time_str = suite.attrib.get("time")
            suite_time = 0.0
            if suite_time_str:
                try:
                    suite_time = float(suite_time_str)
                except ValueError:
                    results["diagnostics"]["warnings"].append(
                        f"Non-float suite time '{suite_time_str}' defaulted to 0.0"
                    )

            results["duration"] += suite_time

            testcases = suite.findall(".//testcase")
            for case in testcases:
                case_name = case.attrib.get("name")
                if not case_name:
                    results["diagnostics"]["warnings"].append("Test case missing 'name' attribute, skipped.")
                    continue

                results["total_tests"] += 1

                case_time_str = case.attrib.get("time")
                case_time = 0.0
                if case_time_str:
                    try:
                        case_time = float(case_time_str)
                    except ValueError:
                        results["diagnostics"]["warnings"].append(
                            f"Non-float testcase time '{case_time_str}' defaulted to 0.0 for {case_name}"
                        )
                else:
                    results["diagnostics"]["warnings"].append(
                        f"Missing duration defaulted to 0.0 for {case_name}"
                    )

                # Determine status
                status = "passed"
                failure_msg = None
                stack_trace = None

                failure_elem = case.find("failure")
                error_elem = case.find("error")
                skipped_elem = case.find("skipped")

                if failure_elem is not None:
                    status = "failed"
                    results["failed_tests"] += 1
                    failure_msg = failure_elem.attrib.get("message")
                    stack_trace = failure_elem.text
                elif error_elem is not None:
                    status = "error"
                    results["failed_tests"] += 1
                    failure_msg = error_elem.attrib.get("message")
                    stack_trace = error_elem.text
                elif skipped_elem is not None:
                    status = "skipped"
                    results["skipped_tests"] += 1
                    failure_msg = skipped_elem.attrib.get("message")
                else:
                    results["passed_tests"] += 1

                # Parse testcase properties
                case_props = SafeJUnitParser._parse_case_properties(case)
                title = case_props.get("title")
                veriscope_ac_key = case_props.get("veriscope_ac_key")
                ac_display_ref = case_props.get("acceptance_criterion_display_ref") or case_props.get("ac_display_ref")
                ac_text = case_props.get("acceptance_criterion_text") or case_props.get("ac_text")
                req_group = case_props.get("requirement_group") or case_props.get("group")
                business_flow = case_props.get("business_flow") or case_props.get("flow")
                acceptance_criterion = veriscope_ac_key or ac_display_ref or case_props.get("acceptance_criterion")
                testing_type = case_props.get("testing_type")
                execution_layer = case_props.get("execution_layer")
                declared_covered_file = case_props.get("covered_file")

                # Map testing_type to test_type and categories
                type_map = SafeJUnitParser._map_testing_type(testing_type)
                test_type = type_map["test_type"]
                test_categories = type_map["test_categories"]

                # Map execution_layer
                exec_map = SafeJUnitParser._map_execution_layer(execution_layer)
                mapped_execution_layer = exec_map["execution_layer"]
                execution_layers = exec_map["execution_layers"]

                # If no testing_type provided, try to infer from execution_layer
                if not testing_type and execution_layer:
                    inferred = SafeJUnitParser._infer_type_from_execution_layer(execution_layer)
                    if inferred:
                        test_type = inferred

                # Fallback inference from name patterns if still unknown
                if test_type == "unknown":
                    test_type = SafeJUnitParser._infer_type_from_name_patterns(
                        suite_name, case_name, declared_covered_file
                    )

                # Rich Taxonomy Mapping Logic
                test_nature = "unknown"
                primary_test_category = "unknown"
                suite_purpose = "unknown"
                risk_tags = []
                import_source = "manual_junit_upload"
                execution_method = "automated"
                framework = "junit_compatible"
                external_ac_ref = acceptance_criterion

                if testing_type:
                    testing_type_lower = testing_type.lower()
                    if "regression/security" in testing_type_lower:
                        test_type = "functional"
                        test_nature = "functional"
                        primary_test_category = "functional"
                        suite_purpose = "regression"
                        risk_tags = ["security"]
                    else:
                        if "regression" in testing_type_lower:
                            suite_purpose = "regression"
                        if "security" in testing_type_lower:
                            risk_tags.append("security")
                        
                        if any(t in testing_type_lower for t in ["unit", "api", "integration", "ui", "e2e"]):
                            test_nature = "automated"
                            for t in ["unit", "api", "integration", "ui", "e2e"]:
                                if t in testing_type_lower:
                                    primary_test_category = t
                                    break
                        else:
                            test_nature = "functional"
                            primary_test_category = "functional"
                else:
                    if test_type in ["unit", "api", "integration", "ui", "e2e"]:
                        test_nature = "automated"
                        primary_test_category = test_type
                    elif test_type in ["regression", "smoke"]:
                        test_nature = "functional"
                        primary_test_category = "functional"
                        suite_purpose = test_type
                    else:
                        test_nature = "functional"
                        primary_test_category = "functional"

                # Stable identity generation (unchanged)
                stable_identity = f"{suite_name}::{case_name}"
                canonical_identity_hash = hashlib.sha256(stable_identity.encode("utf-8")).hexdigest()

                # Parameter stripping
                normalized_test_name = case_name
                normalized_identity_strategy = "RAW"
                if "[" in case_name and case_name.endswith("]"):
                    normalized_test_name = re.sub(r"\[.*\]$", "", case_name)
                    normalized_identity_strategy = "PARAMETER_STRIPPED"
                elif "(" in case_name and case_name.endswith(")"):
                    normalized_test_name = re.sub(r"\(.*\)$", "", case_name)
                    normalized_identity_strategy = "PARAMETER_STRIPPED"

                # File path inference
                file_path = declared_covered_file
                if not file_path:
                    class_path = suite_name.replace(".", "/").replace("::", "/")
                    if class_path.endswith("Test") or class_path.endswith("Tests"):
                        file_path = f"{class_path}.py"
                    elif class_path:
                        file_path = class_path

                dedupe_key = stable_identity

                source_metadata = {
                    "parser": "junit_parser.v1",
                    "suite_name": suite_name,
                    "classname": case.attrib.get("classname", ""),
                    "file_path": file_path,
                    "declared_covered_file": declared_covered_file,
                    "declared_ac_id": acceptance_criterion,
                    "acceptance_criterion": acceptance_criterion,
                    "veriscope_ac_key": veriscope_ac_key,
                    "acceptance_criterion_display_ref": ac_display_ref,
                    "acceptance_criterion_text": ac_text,
                    "requirement_group": req_group,
                    "business_flow": business_flow,
                    "title": title,
                    "testing_type": testing_type,
                    "execution_layer": execution_layer,
                    "mapped_execution_layer": mapped_execution_layer,
                    "execution_layers": execution_layers,
                    "test_categories": test_categories,
                    # New taxonomy metadata
                    "test_nature": test_nature,
                    "primary_test_category": primary_test_category,
                    "suite_purpose": suite_purpose,
                    "risk_tags": risk_tags,
                    "import_source": import_source,
                    "execution_method": execution_method,
                    "framework": framework,
                    "external_ac_ref": external_ac_ref,
                }

                results["test_cases"].append({
                    "suite_name": suite_name,
                    "test_name": case_name,
                    "title": title,
                    "stable_identity": stable_identity,
                    "canonical_identity_hash": canonical_identity_hash,
                    "raw_test_name": case_name,
                    "normalized_test_name": normalized_test_name,
                    "normalized_identity_strategy": normalized_identity_strategy,
                    "framework_name": "junit_compatible",
                    "framework_version": None,
                    "identity_normalization_version": 1,
                    "test_type": test_type,
                    "test_categories": test_categories,
                    "automation_status": "automated",
                    "source": "manual_junit_upload",
                    "source_metadata_json": source_metadata,
                    "file_path": file_path,
                    "dedupe_key": dedupe_key,
                    "is_active": True,
                    "confidence": 1.0,
                    "status": status,
                    "duration": case_time,
                    "failure_message": failure_msg,
                    "stack_trace": stack_trace,
                    "declared_ac_id": acceptance_criterion,
                    "declared_covered_file": declared_covered_file,
                    "acceptance_criterion": acceptance_criterion,
                    "testing_type": testing_type,
                    "execution_layer": mapped_execution_layer,
                    "execution_layers": execution_layers,
                    # Add fields to dict
                    "test_nature": test_nature,
                    "primary_test_category": primary_test_category,
                    "suite_purpose": suite_purpose,
                    "risk_tags": risk_tags,
                    "import_source": import_source,
                    "execution_method": execution_method,
                    "framework": framework,
                    "external_ac_ref": external_ac_ref,
                })

        # Sanity check total XML counts vs parsed results
        xml_declared_tests = root.attrib.get("tests")
        if xml_declared_tests:
            try:
                declared_count = int(xml_declared_tests)
                results["xml_declared_tests"] = declared_count
            except ValueError:
                results["xml_declared_tests"] = None
        else:
            results["xml_declared_tests"] = None

        return results

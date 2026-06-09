import hashlib
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
            # Fallback: search recursively for any testsuite tags
            suites.extend(root.findall(".//testsuite"))
            
        if not suites and root.findall(".//testcase"):
            # If no testsuite tags but testcases exist, treat root as a suite stub
            suites.append(root)

        for suite_idx, suite in enumerate(suites):
            suite_name = suite.attrib.get("name", f"suite_{suite_idx}")
            
            # Suite level duration
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
                
                # Case level duration
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

                # Clean stable identity naming & Framework-aware parameter stripping
                stable_identity = f"{suite_name}::{case_name}"
                canonical_identity_hash = hashlib.sha256(stable_identity.encode("utf-8")).hexdigest()

                # Basic parameter-stripping strategy (extract base name e.g. test_login[user1] -> test_login)
                normalized_test_name = case_name
                normalized_identity_strategy = "RAW"
                if "[" in case_name and case_name.endswith("]"):
                    normalized_test_name = re.sub(r"\[.*\]$", "", case_name)
                    normalized_identity_strategy = "PARAMETER_STRIPPED"
                elif "(" in case_name and case_name.endswith(")"):
                    normalized_test_name = re.sub(r"\(.*\)$", "", case_name)
                    normalized_identity_strategy = "PARAMETER_STRIPPED"

                results["test_cases"].append({
                    "suite_name": suite_name,
                    "test_name": case_name,
                    "stable_identity": stable_identity,
                    "canonical_identity_hash": canonical_identity_hash,
                    "raw_test_name": case_name,
                    "normalized_test_name": normalized_test_name,
                    "normalized_identity_strategy": normalized_identity_strategy,
                    "framework_name": "pytest", # Default framework for Veriscope python test files
                    "framework_version": None,
                    "identity_normalization_version": 1,
                    "status": status,
                    "duration": case_time,
                    "failure_message": failure_msg,
                    "stack_trace": stack_trace
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

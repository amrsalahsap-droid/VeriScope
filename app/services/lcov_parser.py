import os
import re
from typing import List, Dict, Any, Optional

class LCOVParsingError(ValueError):
    """Custom exception raised when LCOV parsing fails or violates safety bounds."""
    pass

class SafeLCOVParser:
    @staticmethod
    def normalize_path(path_str: str) -> str:
        """
        Normalizes a source file path to be a clean relative path with forward slashes.
        Strips absolute prefixes, backslashes, and workspace structures.
        """
        if not path_str:
            return ""
        
        # 1. Standardize separators
        path_str = path_str.replace("\\", "/").strip()
        
        # 2. Extract portion after workspace directory if absolute or deep
        # If it's a typical absolute path like /Users/username/project/app/file.py or C:/project/app/file.py,
        # we can strip out standard workspace roots if they appear.
        # Specifically, we look for 'veriscope/' or similar pattern, or keep the relative tail.
        marker = "veriscope/"
        if marker in path_str:
            parts = path_str.split(marker, 1)
            path_str = parts[1]
        
        # Strip leading slashes
        path_str = re.sub(r"^/+", "", path_str)
        return path_str

    @classmethod
    def parse_lcov(
        cls,
        content_str: str,
        max_records: int = 10000,
        max_lines_per_file: int = 100000
    ) -> List[Dict[str, Any]]:
        """
        Streaming-style parser for LCOV files. Processes line-by-line safely.
        
        Returns:
            List of dictionaries sorted alphabetically by file_path:
            [
              {
                "file_path": "app/services/auth.py",
                "test_name": "test_auth_flow",  # Optional, from TN: tag
                "covered_lines": [1, 2, 5],
                "uncovered_lines": [3, 4],
                "total_lines_count": 5,
                "covered_lines_count": 3,
                "uncovered_lines_count": 2,
                "total_lines": 5,
                "line_coverage_ratio": 0.6,
                "branch_coverage_ratio": 0.5,
                "functions_covered": 1,
                "functions_total": 2
              }
            ]
        """
        records = []
        current_record: Optional[Dict[str, Any]] = None
        current_test_name: str = ""
        
        # Guard against massive input string by processing line-by-line
        lines = content_str.splitlines()
        
        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            if not line:
                continue
            
            # 1. Parse Test Name (TN:test_name)
            if line.startswith("TN:"):
                current_test_name = line[3:].strip()
                continue
            
            # 2. Start of Source File record (SF:file_path)
            elif line.startswith("SF:"):
                if len(records) >= max_records:
                    raise LCOVParsingError(
                        f"LCOV report contains too many file records (exceeded safety limit of {max_records})."
                    )
                
                raw_path = line[3:].strip()
                normalized_path = cls.normalize_path(raw_path)
                
                current_record = {
                    "file_path": normalized_path,
                    "test_name": current_test_name,
                    "covered_lines": set(),
                    "uncovered_lines": set(),
                    "total_lines_count": 0,
                    "covered_lines_count": 0,
                    "uncovered_lines_count": 0,
                    "total_lines": 0,
                    "line_coverage_ratio": 0.0,
                    "branch_coverage_ratio": None,
                    "functions_covered": None,
                    "functions_total": None,
                    "brf": None,
                    "brh": None,
                    "lf": None,
                    "lh": None
                }
                continue
            
            # 3. Line coverage data (DA:line,exec_count[,checksum])
            elif line.startswith("DA:"):
                if not current_record:
                    continue
                
                data_part = line[3:].strip()
                parts = data_part.split(",")
                if len(parts) < 2:
                    raise LCOVParsingError(
                        f"Malformed LCOV DA tag on line {line_num}: '{line}'"
                    )
                
                try:
                    stmt_line = int(parts[0])
                    exec_count = int(parts[1])
                except ValueError:
                    raise LCOVParsingError(
                        f"Invalid integer values in LCOV DA tag on line {line_num}: '{line}'"
                    )
                
                if stmt_line < 0 or exec_count < 0:
                    raise LCOVParsingError(
                        f"Invalid negative values in LCOV DA tag on line {line_num}: '{line}'"
                    )
                
                total_lines_for_file = len(current_record["covered_lines"]) + len(current_record["uncovered_lines"])
                if total_lines_for_file >= max_lines_per_file:
                    raise LCOVParsingError(
                        f"File '{current_record['file_path']}' exceeded statement safety limit of {max_lines_per_file} lines."
                    )
                
                if exec_count > 0:
                    current_record["covered_lines"].add(stmt_line)
                    current_record["uncovered_lines"].discard(stmt_line)
                else:
                    if stmt_line not in current_record["covered_lines"]:
                        current_record["uncovered_lines"].add(stmt_line)
                continue
            
            # 4. Function Totals tags (FNF, FNH)
            elif line.startswith("FNF:"):
                if not current_record:
                    continue
                val = line[4:].strip()
                try:
                    current_record["functions_total"] = int(val)
                except ValueError:
                    raise LCOVParsingError(
                        f"Invalid integer value in FNF tag on line {line_num}: '{line}'"
                    )
                if current_record["functions_total"] < 0:
                    raise LCOVParsingError(
                        f"Negative value in FNF tag on line {line_num}: '{line}'"
                    )
                continue

            elif line.startswith("FNH:"):
                if not current_record:
                    continue
                val = line[4:].strip()
                try:
                    current_record["functions_covered"] = int(val)
                except ValueError:
                    raise LCOVParsingError(
                        f"Invalid integer value in FNH tag on line {line_num}: '{line}'"
                    )
                if current_record["functions_covered"] < 0:
                    raise LCOVParsingError(
                        f"Negative value in FNH tag on line {line_num}: '{line}'"
                    )
                continue

            # 5. Branch Totals tags (BRF, BRH)
            elif line.startswith("BRF:"):
                if not current_record:
                    continue
                val = line[4:].strip()
                try:
                    current_record["brf"] = int(val)
                except ValueError:
                    raise LCOVParsingError(
                        f"Invalid integer value in BRF tag on line {line_num}: '{line}'"
                    )
                if current_record["brf"] < 0:
                    raise LCOVParsingError(
                        f"Negative value in BRF tag on line {line_num}: '{line}'"
                    )
                continue

            elif line.startswith("BRH:"):
                if not current_record:
                    continue
                val = line[4:].strip()
                try:
                    current_record["brh"] = int(val)
                except ValueError:
                    raise LCOVParsingError(
                        f"Invalid integer value in BRH tag on line {line_num}: '{line}'"
                    )
                if current_record["brh"] < 0:
                    raise LCOVParsingError(
                        f"Negative value in BRH tag on line {line_num}: '{line}'"
                    )
                continue

            # 6. Line Totals tags (LF, LH)
            elif line.startswith("LF:"):
                if not current_record:
                    continue
                val = line[3:].strip()
                try:
                    current_record["lf"] = int(val)
                except ValueError:
                    raise LCOVParsingError(
                        f"Invalid integer value in LF tag on line {line_num}: '{line}'"
                    )
                if current_record["lf"] < 0:
                    raise LCOVParsingError(
                        f"Negative value in LF tag on line {line_num}: '{line}'"
                    )
                continue

            elif line.startswith("LH:"):
                if not current_record:
                    continue
                val = line[3:].strip()
                try:
                    current_record["lh"] = int(val)
                except ValueError:
                    raise LCOVParsingError(
                        f"Invalid integer value in LH tag on line {line_num}: '{line}'"
                    )
                if current_record["lh"] < 0:
                    raise LCOVParsingError(
                        f"Negative value in LH tag on line {line_num}: '{line}'"
                    )
                continue

            # 7. End of Record terminator (end_of_record)
            elif line == "end_of_record":
                if current_record:
                    covered = sorted(list(current_record["covered_lines"]))
                    uncovered = sorted(list(current_record["uncovered_lines"]))
                    
                    total_lines = len(covered) + len(uncovered)
                    
                    # Ignore empty records (records with 0 lines and no parsed totals)
                    if total_lines == 0 and current_record.get("functions_total") is None and current_record.get("brf") is None:
                        current_record = None
                        current_test_name = ""
                        continue
                    
                    current_record["covered_lines"] = covered
                    current_record["uncovered_lines"] = uncovered
                    current_record["covered_lines_count"] = len(covered)
                    current_record["uncovered_lines_count"] = len(uncovered)
                    current_record["total_lines_count"] = total_lines
                    current_record["total_lines"] = total_lines
                    
                    # Compute line coverage ratio
                    current_record["line_coverage_ratio"] = (len(covered) / total_lines) if total_lines > 0 else 0.0
                    
                    # Compute branch coverage ratio
                    brf = current_record.get("brf")
                    brh = current_record.get("brh")
                    if brf is not None and brf > 0:
                        current_record["branch_coverage_ratio"] = (brh / brf) if brh is not None else 0.0
                    else:
                        current_record["branch_coverage_ratio"] = None
                    
                    records.append(current_record)
                    current_record = None
                    current_test_name = ""
                continue
        
        if not records:
            raise LCOVParsingError("No valid SF records found in LCOV content.")
            
        # Deterministic alphabetical ordering by file_path
        records.sort(key=lambda x: x["file_path"])
        return records

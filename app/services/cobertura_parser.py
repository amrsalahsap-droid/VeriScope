import re
from typing import List, Dict, Any, Optional
from defusedxml.ElementTree import fromstring, ParseError
from app.services.lcov_parser import SafeLCOVParser

class CoberturaParsingError(ValueError):
    """Custom exception raised when Cobertura parsing fails or violates safety bounds."""
    pass

class SafeCoberturaParser:
    @classmethod
    def parse_cobertura(
        cls,
        content_str: str,
        max_records: int = 10000,
        max_lines_per_file: int = 100000
    ) -> Dict[str, Any]:
        """
        Parses Cobertura XML string securely using defusedxml.
        Strictly rejects external entity expansion (XXE).
        
        Returns:
            Dict containing files records list and overall aggregated ratios:
            {
              "files": [
                {
                  "file_path": "app/services/auth.py",
                  "covered_lines": [1, 2, 5],
                  "uncovered_lines": [3, 4],
                  "total_lines_count": 5,
                  "covered_lines_count": 3,
                  "uncovered_lines_count": 2,
                  "branch_coverage_ratio": 0.8,
                  "functions_covered": 2,
                  "functions_total": 3
                }
              ],
              "overall_line_coverage_ratio": 0.85,
              "overall_branch_coverage_ratio": 0.80
            }
        """
        try:
            root = fromstring(content_str)
        except ParseError as e:
            raise CoberturaParsingError(f"Malformed Cobertura XML payload: {str(e)}")
        except Exception as e:
            raise CoberturaParsingError(f"Security or structural parsing block: {str(e)}")

        # Extract overall coverage ratios from root node attributes
        overall_line_ratio = None
        line_rate_str = root.attrib.get("line-rate")
        if line_rate_str:
            try:
                overall_line_ratio = float(line_rate_str)
            except ValueError:
                pass

        overall_branch_ratio = None
        branch_rate_str = root.attrib.get("branch-rate")
        if branch_rate_str:
            try:
                overall_branch_ratio = float(branch_rate_str)
            except ValueError:
                pass

        records = []
        classes = root.findall(".//class")
        
        if not classes:
            raise CoberturaParsingError("No class elements found in Cobertura XML content.")
        
        if len(classes) > max_records:
            raise CoberturaParsingError(
                f"Cobertura report contains too many class records (exceeded safety limit of {max_records})."
            )
            
        for clazz in classes:
            file_path = clazz.attrib.get("filename")
            if not file_path:
                continue
                
            normalized_path = SafeLCOVParser.normalize_path(file_path)
            
            # Line-level statement tracking
            covered_lines = set()
            uncovered_lines = set()
            
            lines = clazz.findall(".//line")
            if len(lines) > max_lines_per_file:
                raise CoberturaParsingError(
                    f"File '{normalized_path}' exceeded statement safety limit of {max_lines_per_file} lines."
                )
                
            total_branches = 0
            covered_branches = 0
            
            for line in lines:
                try:
                    stmt_line = int(line.attrib["number"])
                    hits = int(line.attrib["hits"])
                except (KeyError, ValueError):
                    raise CoberturaParsingError(f"Invalid Cobertura line tag format in file '{normalized_path}'")
                    
                if stmt_line < 0 or hits < 0:
                    raise CoberturaParsingError(f"Invalid negative values in Cobertura line tag in file '{normalized_path}'")

                if hits > 0:
                    covered_lines.add(stmt_line)
                else:
                    uncovered_lines.add(stmt_line)
                    
                # Branch tracking: branch="true"
                is_branch = line.attrib.get("branch", "false").lower() == "true"
                if is_branch:
                    cond = line.attrib.get("condition-coverage")
                    if cond:
                        # e.g., "50% (1/2)" or "100% (2/2)"
                        match = re.search(r"\((?P<cov>\d+)/(?P<tot>\d+)\)", cond)
                        if match:
                            covered_branches += int(match.group("cov"))
                            total_branches += int(match.group("tot"))
                        else:
                            total_branches += 2
                            covered_branches += 2 if hits > 0 else 0
                    else:
                        total_branches += 2
                        covered_branches += 2 if hits > 0 else 0
                        
            # Function/method tracking: methods inside class
            methods = clazz.findall(".//method")
            functions_total = len(methods) if methods else None
            functions_covered = None
            if methods:
                functions_covered = 0
                for method in methods:
                    method_lines = method.findall(".//line")
                    if method_lines:
                        if any(int(ml.attrib.get("hits", 0)) > 0 for ml in method_lines):
                            functions_covered += 1
                    else:
                        line_rate_str = method.attrib.get("line-rate")
                        if line_rate_str:
                            try:
                                if float(line_rate_str) > 0.0:
                                    functions_covered += 1
                            except ValueError:
                                pass
                                
            branch_ratio = None
            if total_branches > 0:
                branch_ratio = covered_branches / total_branches
                
            covered_list = sorted(list(covered_lines))
            uncovered_list = sorted(list(uncovered_lines))
            
            fe_total = len(covered_list) + len(uncovered_list)
            fe_ratio = (len(covered_list) / fe_total) if fe_total > 0 else 0.0

            records.append({
                "file_path": normalized_path,
                "covered_lines": covered_list,
                "uncovered_lines": uncovered_list,
                "total_lines": fe_total,
                "line_coverage_ratio": fe_ratio,
                "branch_coverage_ratio": branch_ratio,
                
                # Legacy / backward compatibility
                "total_lines_count": fe_total,
                "covered_lines_count": len(covered_list),
                "uncovered_lines_count": len(uncovered_list),
                "functions_covered": functions_covered,
                "functions_total": functions_total
            })
            
        total_xml_lines = sum(r["total_lines"] for r in records)
        if total_xml_lines == 0:
            raise CoberturaParsingError("No valid coverage line elements found in Cobertura XML content.")

        # Deterministic alphabetical ordering by file_path
        records.sort(key=lambda x: x["file_path"])

        return {
            "files": records,
            "overall_line_coverage_ratio": overall_line_ratio,
            "overall_branch_coverage_ratio": overall_branch_ratio
        }

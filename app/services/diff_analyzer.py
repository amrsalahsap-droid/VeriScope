"""Semantic Diff Analyzer for Phase 8

Extracts semantic information from PR diffs to understand what changed
at a code level (functions, rules, conditionals, constants).
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.models.change_summary import ChangeSummary, ConstantChange
from app.schemas.regression_scope_v2 import ChangeSummary as LegacyChangeSummary, ChangedRule


@dataclass
class DiffLine:
    """Represents a single line in a unified diff."""
    line_type: str  # '+', '-', ' ', or '@@'
    content: str
    line_number: Optional[int] = None
    old_line_number: Optional[int] = None


class DiffAnalyzer:
    """Analyzes unified diffs to extract semantic change information."""
    
    # ==========================================
    # New Semantic Diff Analyzer (Phase 1)
    # ==========================================

    # Domain terms to detect
    DOMAIN_TERMS = ['password', 'token', 'reset', 'login', 'signup', 'sign-up',
                    'update-password', 'validation', 'auth', 'credential', 'session']

    # Validation patterns
    VALIDATION_PATTERNS = [
        (r'\.test\(/', 'regex test'),
        (r'\.match\(/', 'regex match'),
        (r'min_?length\s*[:=]\s*(\d+)', 'min length'),
        (r'max_?length\s*[:=]\s*(\d+)', 'max length'),
        (r'uppercase', 'uppercase required'),
        (r'lowercase', 'lowercase required'),
        (r'specialChar', 'special character required'),
        (r'password\.length', 'password length check'),
        (r'token\.expir', 'token expiry check'),
    ]

    @staticmethod
    def analyze(pr_diff_text: str, changed_file_paths: List[str]) -> Dict[str, ChangeSummary]:
        """
        Parse unified diff and return a dict mapping file path -> ChangeSummary.
        """
        file_diffs = DiffAnalyzer._split_by_file(pr_diff_text, changed_file_paths)
        summaries = {}
        for file_path, diff_hunks in file_diffs.items():
            summary = ChangeSummary(file_path=file_path)
            DiffAnalyzer._extract_changed_functions(diff_hunks, summary)
            DiffAnalyzer._extract_new_conditionals(diff_hunks, summary)
            DiffAnalyzer._extract_modified_constants(diff_hunks, summary)
            DiffAnalyzer._extract_validations(diff_hunks, summary)
            DiffAnalyzer._extract_domain_terms(diff_hunks, summary)
            summaries[file_path] = summary
        return summaries

    @staticmethod
    def _split_by_file(diff_text: str, file_paths: List[str]) -> Dict[str, str]:
        if not diff_text:
            return {path: "" for path in file_paths}
        
        file_diffs = {}
        current_file = None
        current_lines = []
        path_set = set(file_paths)
        
        for line in diff_text.split('\n'):
            if line.startswith('diff --git'):
                if current_file and current_lines:
                    file_diffs[current_file] = '\n'.join(current_lines)
                    current_lines = []
                
                current_file = None
                for path in path_set:
                    if f" b/{path}" in line:
                        current_file = path
                        break
                if not current_file:
                    match = re.search(r' b/(.+)$', line)
                    if match and match.group(1) in path_set:
                        current_file = match.group(1)
            elif current_file is not None:
                current_lines.append(line)
                
        if current_file and current_lines:
            file_diffs[current_file] = '\n'.join(current_lines)
            
        for path in file_paths:
            if path not in file_diffs:
                file_diffs[path] = ""
                
        return file_diffs

    @staticmethod
    def _extract_changed_functions(diff_hunks: str, summary: ChangeSummary):
        # Look for function definitions in + and - lines
        func_patterns = [
            re.compile(r'\bdef\s+([\w]+)\s*\('),                              # Python def
            re.compile(r'\bfunction\s+([\w]+)\b'),                           # JS function
            re.compile(r'\bconst\s+([\w]+)\s*=\s*(?:async\s*)?\('),          # JS arrow function
            re.compile(r'\b([\w]+)\s*\([^)]*\)\s*\{'),                        # JS method / C-style function
        ]
        keywords = {'if', 'for', 'while', 'switch', 'catch', 'with', 'elif', 'else'}
        for line in diff_hunks.split('\n'):
            if line.startswith('+') or line.startswith('-'):
                code = line[1:].strip()
                # Skip comments
                if code.startswith('//') or code.startswith('#') or code.startswith('/*') or code.startswith('*'):
                    continue
                for pattern in func_patterns:
                    for name in pattern.findall(code):
                        if name and name not in keywords and name not in summary.changed_functions:
                            summary.changed_functions.append(name)

    @staticmethod
    def _extract_new_conditionals(diff_hunks: str, summary: ChangeSummary):
        # Look for added lines (starting with +) that introduce new conditionals
        # Support JS/TS (if, else if, switch, catch, ternary) and Python (if, elif, except)
        cond_pattern = re.compile(
            r'('
            r'\bif\s*\(.+\)|'
            r'\belse\s+if\s*\(.+\)|'
            r'\bswitch\s*\(.+\)|'
            r'\bcatch\s*\(.+\)|'
            r'\bif\s+[^:]+:|'
            r'\belif\s+[^:]+:|'
            r'\bexcept(?:\s+[^:]+)?\s*:|'
            r'\?[\s\S]*?:'
            r')'
        )
        for line in diff_hunks.split('\n'):
            if line.startswith('+'):
                code = line[1:].strip()
                if code.startswith('//') or code.startswith('#') or code.startswith('/*') or code.startswith('*'):
                    continue
                if cond_pattern.search(code):
                    summary.new_conditionals.append(code)

    @staticmethod
    def _extract_modified_constants(diff_hunks: str, summary: ChangeSummary):
        removed_lines = []
        added_lines = []
        for line in diff_hunks.split('\n'):
            if line.startswith('-'):
                code = line[1:].strip()
                if not (code.startswith('//') or code.startswith('#') or code.startswith('/*') or code.startswith('*')):
                    removed_lines.append(code)
            elif line.startswith('+'):
                code = line[1:].strip()
                if not (code.startswith('//') or code.startswith('#') or code.startswith('/*') or code.startswith('*')):
                    added_lines.append(code)
        
        js_pattern = re.compile(r'^(?:const|let|var)\s+([\w]+)\s*=\s*(.+)$')
        py_pattern = re.compile(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$')
        
        def parse_constant(line_str: str):
            js_match = js_pattern.match(line_str)
            if js_match:
                name = js_match.group(1)
                val = js_match.group(2).rstrip(';').strip()
                return name, val
            py_match = py_pattern.match(line_str)
            if py_match:
                name = py_match.group(1)
                val = py_match.group(2).strip()
                return name, val
            return None

        removed_constants = {}
        for rline in removed_lines:
            parsed = parse_constant(rline)
            if parsed:
                name, val = parsed
                removed_constants[name] = val
        
        for aline in added_lines:
            parsed = parse_constant(aline)
            if parsed:
                name, new_val = parsed
                if name in removed_constants:
                    old_val = removed_constants[name]
                    if old_val != new_val:
                        summary.modified_constants.append(ConstantChange(name=name, old_value=old_val, new_value=new_val))

    @staticmethod
    def _extract_validations(diff_hunks: str, summary: ChangeSummary):
        for line in diff_hunks.split('\n'):
            if line.startswith('+'):
                code = line[1:].strip()
                if code.startswith('//') or code.startswith('#') or code.startswith('/*') or code.startswith('*'):
                    continue
                for pattern, desc in DiffAnalyzer.VALIDATION_PATTERNS:
                    if re.search(pattern, code, re.IGNORECASE):
                        if desc not in summary.added_validations:
                            summary.added_validations.append(desc)
            elif line.startswith('-'):
                code = line[1:].strip()
                if code.startswith('//') or code.startswith('#') or code.startswith('/*') or code.startswith('*'):
                    continue
                for pattern, desc in DiffAnalyzer.VALIDATION_PATTERNS:
                    if re.search(pattern, code, re.IGNORECASE):
                        if desc not in summary.removed_validations:
                            summary.removed_validations.append(desc)

    @staticmethod
    def _extract_domain_terms(diff_hunks: str, summary: ChangeSummary):
        for line in diff_hunks.split('\n'):
            if line.startswith('+') or line.startswith('-'):
                code = line[1:].strip()
                for term in DiffAnalyzer.DOMAIN_TERMS:
                    if term in code.lower() and term not in summary.affected_domain_terms:
                        summary.affected_domain_terms.append(term)


    # ==========================================
    # Legacy Backward-Compatibility Adapters
    # ==========================================
    
    # Legacy patterns
    FUNCTION_PATTERNS = [
        r'function\s+(\w+)',  # JavaScript/TypeScript function
        r'const\s+(\w+)\s*=\s*\(',  # Arrow function
        r'async\s+(\w+)\s*\(',  # Async function
        r'def\s+(\w+)\s*\(',  # Python function
        r'(\w+)\s*\([^)]*\)\s*{',  # C-style function
    ]
    
    RULE_PATTERNS = [
        r'minLength',
        r'maxLength',
        r'uppercase',
        r'lowercase',
        r'specialChar',
        r'expir',
        r'token',
        r'validatePassword',
        r'password\.length',
        r'require\(',
        r'assert\(',
    ]
    
    LEGACY_DOMAIN_TERMS = [
        'password',
        'token',
        'reset',
        'expiry',
        'expire',
        'auth',
        'login',
        'signup',
        'sign-up',
        'credential',
    ]
    
    @staticmethod
    def parse_unified_diff(diff_text: str) -> Dict[str, List[DiffLine]]:
        files = {}
        current_file = None
        current_lines = []
        
        for line in diff_text.split('\n'):
            if line.startswith('diff --git'):
                if current_file and current_lines:
                    files[current_file] = current_lines
                match = re.search(r'b/(.+)', line)
                if match:
                    current_file = match.group(1)
                else:
                    current_file = 'unknown'
                current_lines = []
            elif line.startswith('+++'):
                match = re.search(r'b/(.+)', line)
                if match:
                    current_file = match.group(1)
                current_lines = []
            elif line.startswith('@@'):
                continue
            elif line and (line.startswith('+') or line.startswith('-') or line.startswith(' ')):
                line_type = line[0]
                content = line[1:]
                current_lines.append(DiffLine(line_type=line_type, content=content))
        
        if current_file and current_lines:
            files[current_file] = current_lines
        
        return files
    
    @staticmethod
    def extract_changed_functions(lines: List[DiffLine]) -> List[str]:
        functions = set()
        for line in lines:
            if line.line_type == '+':
                for pattern in DiffAnalyzer.FUNCTION_PATTERNS:
                    matches = re.findall(pattern, line.content)
                    for match in matches:
                        functions.add(match)
        return list(functions)
    
    @staticmethod
    def extract_changed_rules(lines: List[DiffLine], file_path: str) -> List[ChangedRule]:
        rules = []
        for idx, line in enumerate(lines):
            if line.line_type == '+':
                for pattern in DiffAnalyzer.RULE_PATTERNS:
                    if re.search(pattern, line.content, re.IGNORECASE):
                        rule_type = 'validation'
                        if 'token' in pattern.lower() or 'expir' in pattern.lower():
                            rule_type = 'security'
                        elif 'assert' in pattern.lower() or 'require' in pattern.lower():
                            rule_type = 'business_logic'
                        rules.append(ChangedRule(
                            rule_name=pattern,
                            rule_type=rule_type,
                            file_path=file_path,
                            line_number=idx
                        ))
                        break
        return rules
    
    @staticmethod
    def count_new_conditionals(lines: List[DiffLine]) -> int:
        count = 0
        conditional_keywords = ['if', 'else if', 'elif', 'switch', 'case', 'catch']
        for line in lines:
            if line.line_type == '+':
                content_stripped = line.content.strip()
                for keyword in conditional_keywords:
                    if content_stripped.startswith(keyword):
                        count += 1
                        break
        return count
    
    @staticmethod
    def extract_changed_constants(lines: List[DiffLine]) -> List[str]:
        constants = []
        for line in lines:
            if line.line_type == '+':
                string_matches = re.findall(r'["\']([^"\']+)["\']', line.content)
                for match in string_matches:
                    if len(match) > 3 and any(char.isalpha() for char in match):
                        constants.append(match)
                number_matches = re.findall(r'\b(\d{1,3})\b', line.content)
                for match in number_matches:
                    if int(match) > 5 and int(match) < 1000:
                        constants.append(match)
        return constants
    
    @staticmethod
    def extract_legacy_domain_terms(lines: List[DiffLine]) -> List[str]:
        terms = set()
        for line in lines:
            if line.line_type == '+':
                content_lower = line.content.lower()
                for term in DiffAnalyzer.LEGACY_DOMAIN_TERMS:
                    if term in content_lower:
                        terms.add(term)
        return list(terms)
    
    @staticmethod
    def analyze_file_diff(file_path: str, lines: List[DiffLine]) -> LegacyChangeSummary:
        return LegacyChangeSummary(
            file_path=file_path,
            changed_functions=DiffAnalyzer.extract_changed_functions(lines),
            changed_rules=DiffAnalyzer.extract_changed_rules(lines, file_path),
            new_conditionals=DiffAnalyzer.count_new_conditionals(lines),
            changed_constants=DiffAnalyzer.extract_changed_constants(lines),
            affected_domain_terms=DiffAnalyzer.extract_legacy_domain_terms(lines)
        )
    
    @staticmethod
    def analyze_pr_diff(diff_text: str) -> List[LegacyChangeSummary]:
        file_diffs = DiffAnalyzer.parse_unified_diff(diff_text)
        summaries = []
        for file_path, lines in file_diffs.items():
            summary = DiffAnalyzer.analyze_file_diff(file_path, lines)
            summaries.append(summary)
        return summaries


def get_pr_diff_from_db(pr_id: str, db) -> Optional[str]:
    """Retrieve the PR diff from the database."""
    from app.models.pull_request import PullRequest
    
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        return None
    
    if hasattr(pr, 'diff_text') and pr.diff_text:
        return pr.diff_text
    
    if hasattr(pr, 'diff') and pr.diff:
        return pr.diff
        
    return None

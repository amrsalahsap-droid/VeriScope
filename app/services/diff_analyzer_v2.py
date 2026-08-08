"""
DiffAnalyzerV2 Service for Semantic Change Detection.

Distinguishes real code changes from comments/formatting and captures
function/condition/constant changes using AST analysis for TypeScript/JavaScript.
"""

import logging
import re
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from app.schemas.change_summary import (
    ChangeSummary,
    FunctionChange,
    ConditionChange,
    ConstantChange,
    ExportChange,
)


class DiffAnalyzerV2:
    """Service for semantic diff analysis of TypeScript/JavaScript files."""
    
    # Supported file extensions for AST parsing
    AST_SUPPORTED_EXTENSIONS = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
    
    # Feature flag for regex fallback
    USE_REGEX_FALLBACK = True
    
    @staticmethod
    def analyze_diff(
        file_path: str,
        content_before: str,
        content_after: str,
        use_ast: bool = True
    ) -> ChangeSummary:
        """Analyze diff between two file contents.
        
        Args:
            file_path: Path to the file
            content_before: Content before change
            content_after: Content after change
            use_ast: Whether to use AST parsing (if supported)
            
        Returns:
            ChangeSummary with semantic change analysis
        """
        file_ext = DiffAnalyzerV2._get_file_extension(file_path)
        
        # Determine if we should use AST parsing
        should_use_ast = use_ast and file_ext in DiffAnalyzerV2.AST_SUPPORTED_EXTENSIONS
        
        if should_use_ast:
            try:
                summary = DiffAnalyzerV2._analyze_with_ast(file_path, content_before, content_after)
                return summary
            except Exception as e:
                logger.warning(f"AST parsing failed for {file_path}: {e}, falling back to regex")
                if DiffAnalyzerV2.USE_REGEX_FALLBACK:
                    return DiffAnalyzerV2._analyze_with_regex(file_path, content_before, content_after, parse_error=str(e))
                else:
                    # Return summary with parse_failed flag
                    return ChangeSummary(
                        file_path=file_path,
                        parser_used="ast",
                        parse_failed=True,
                        parse_error=str(e),
                        fallback_used=False
                    )
        else:
            # Use regex-based analysis for non-TS/JS files or when AST is disabled
            return DiffAnalyzerV2._analyze_with_regex(file_path, content_before, content_after)
    
    @staticmethod
    def _get_file_extension(file_path: str) -> str:
        """Get file extension from path."""
        import os
        return os.path.splitext(file_path)[1].lower()
    
    @staticmethod
    def _analyze_with_ast(
        file_path: str,
        content_before: str,
        content_after: str
    ) -> ChangeSummary:
        """Analyze diff using AST parsing.
        
        For TypeScript/JavaScript files, this uses tree-sitter or similar
        to extract semantic changes.
        
        Args:
            file_path: Path to the file
            content_before: Content before change
            content_after: Content after change
            
        Returns:
            ChangeSummary with AST-based analysis
        """
        # Try to use tree-sitter if available
        try:
            return DiffAnalyzerV2._analyze_with_tree_sitter(file_path, content_before, content_after)
        except ImportError:
            logger.warning("tree-sitter not available, falling back to regex")
            return DiffAnalyzerV2._analyze_with_regex(file_path, content_before, content_after, parse_error="tree-sitter not available")
        except Exception as e:
            logger.error(f"Tree-sitter analysis failed: {e}")
            return DiffAnalyzerV2._analyze_with_regex(file_path, content_before, content_after, parse_error=str(e))
    
    @staticmethod
    def _analyze_with_tree_sitter(
        file_path: str,
        content_before: str,
        content_after: str
    ) -> ChangeSummary:
        """Analyze diff using tree-sitter AST parsing.
        
        This is a placeholder implementation. In a real implementation,
        this would use the tree-sitter library to parse TS/JS ASTs
        and compare them for semantic changes.
        
        Args:
            file_path: Path to the file
            content_before: Content before change
            content_after: Content after change
            
        Returns:
            ChangeSummary with tree-sitter-based analysis
        """
        # Placeholder: In real implementation, this would:
        # 1. Parse both contents with tree-sitter
        # 2. Extract functions, conditions, constants, exports
        # 3. Compare and detect changes
        # 4. Detect non-semantic changes
        
        # For now, fall back to regex
        logger.info("Tree-sitter analysis not fully implemented, using regex fallback")
        return DiffAnalyzerV2._analyze_with_regex(file_path, content_before, content_after, parse_error="tree-sitter not fully implemented")
    
    @staticmethod
    def _analyze_with_regex(
        file_path: str,
        content_before: str,
        content_after: str,
        parse_error: Optional[str] = None
    ) -> ChangeSummary:
        """Analyze diff using regex-based pattern matching.
        
        This is a fallback when AST parsing is not available or fails.
        It uses regex patterns to detect function, condition, and constant changes.
        
        Args:
            file_path: Path to the file
            content_before: Content before change
            content_after: Content after change
            parse_error: Parse error message if AST parsing failed
            
        Returns:
            ChangeSummary with regex-based analysis
        """
        # Split into lines
        lines_before = content_before.split('\n')
        lines_after = content_after.split('\n')
        
        # Calculate total lines changed
        total_lines_changed = DiffAnalyzerV2._count_changed_lines(lines_before, lines_after)
        
        # Detect non-semantic changes
        comments_only = DiffAnalyzerV2._is_comments_only(lines_before, lines_after)
        formatting_only = DiffAnalyzerV2._is_formatting_only(lines_before, lines_after)
        non_semantic_changes_only = comments_only or formatting_only
        
        # Extract semantic changes
        changed_functions = DiffAnalyzerV2._detect_function_changes_regex(lines_before, lines_after)
        added_functions = DiffAnalyzerV2._detect_added_functions_regex(lines_before, lines_after)
        removed_functions = DiffAnalyzerV2._detect_removed_functions_regex(lines_before, lines_after)
        changed_conditions = DiffAnalyzerV2._detect_condition_changes_regex(lines_before, lines_after)
        changed_constants = DiffAnalyzerV2._detect_constant_changes_regex(lines_before, lines_after)
        changed_exports = DiffAnalyzerV2._detect_export_changes_regex(lines_before, lines_after)
        
        # Calculate semantic change count
        semantic_change_count = (
            len(changed_functions) + len(added_functions) + len(removed_functions) +
            len(changed_conditions) + len(changed_constants) + len(changed_exports)
        )
        
        return ChangeSummary(
            file_path=file_path,
            parser_used="regex",
            changed_functions=changed_functions,
            added_functions=added_functions,
            removed_functions=removed_functions,
            changed_conditions=changed_conditions,
            changed_constants=changed_constants,
            changed_exports=changed_exports,
            non_semantic_changes_only=non_semantic_changes_only,
            comments_only=comments_only,
            formatting_only=formatting_only,
            parse_failed=parse_error is not None,
            fallback_used=True,
            parse_error=parse_error,
            total_lines_changed=total_lines_changed,
            semantic_change_count=semantic_change_count
        )
    
    @staticmethod
    def _count_changed_lines(lines_before: List[str], lines_after: List[str]) -> int:
        """Count the number of changed lines between two versions."""
        # Simple line-by-line comparison
        max_lines = max(len(lines_before), len(lines_after))
        changed_count = 0
        
        for i in range(max_lines):
            line_before = lines_before[i] if i < len(lines_before) else ""
            line_after = lines_after[i] if i < len(lines_after) else ""
            
            # Normalize whitespace for comparison
            if line_before.strip() != line_after.strip():
                changed_count += 1
        
        return changed_count
    
    @staticmethod
    def _is_comments_only(lines_before: List[str], lines_after: List[str]) -> bool:
        """Check if only comments changed."""
        # Remove comments from both versions
        def remove_comments(lines):
            result = []
            for line in lines:
                # Remove single-line comments
                line = re.sub(r'//.*$', '', line)
                # Remove multi-line comments (simplified)
                line = re.sub(r'/\*.*?\*/', '', line, flags=re.DOTALL)
                result.append(line)
            return result
        
        no_comments_before = remove_comments(lines_before)
        no_comments_after = remove_comments(lines_after)
        
        # Compare without comments
        return no_comments_before == no_comments_after
    
    @staticmethod
    def _is_formatting_only(lines_before: List[str], lines_after: List[str]) -> bool:
        """Check if only formatting (whitespace) changed."""
        # Normalize whitespace and compare
        def normalize_whitespace(lines):
            return [line.strip() for line in lines]
        
        normalized_before = normalize_whitespace(lines_before)
        normalized_after = normalize_whitespace(lines_after)
        
        return normalized_before == normalized_after
    
    @staticmethod
    def _detect_function_changes_regex(
        lines_before: List[str],
        lines_after: List[str]
    ) -> List[FunctionChange]:
        """Detect function changes using regex."""
        changed_functions = []
        
        # Function pattern: function name(...) or const name = (...) => or export function name(...)
        function_pattern = re.compile(
            r'(?:export\s+)?(?:function|const)\s+(\w+)\s*(?:=|\()',
            re.MULTILINE
        )
        
        functions_before = {name: (idx, line) for idx, line in enumerate(lines_before) 
                           for name in function_pattern.findall(line)}
        functions_after = {name: (idx, line) for idx, line in enumerate(lines_after) 
                          for name in function_pattern.findall(line)}
        
        # Find functions that exist in both but changed
        for name in set(functions_before.keys()) & set(functions_after.keys()):
            idx_before, line_before = functions_before[name]
            idx_after, line_after = functions_after[name]
            
            if line_before != line_after:
                # Check if signature changed
                signature_changed = DiffAnalyzerV2._function_signature_changed(line_before, line_after)
                
                changed_functions.append(FunctionChange(
                    name=name,
                    signature_changed=signature_changed,
                    body_changed=not signature_changed,  # If signature didn't change, body did
                    is_exported='export' in line_before or 'export' in line_after,
                    line_number=idx_after
                ))
        
        return changed_functions
    
    @staticmethod
    def _function_signature_changed(line_before: str, line_after: str) -> bool:
        """Check if function signature changed."""
        # Extract signature (everything before first { or =>)
        sig_before = re.sub(r'\s*[\{=>].*$', '', line_before).strip()
        sig_after = re.sub(r'\s*[\{=>].*$', '', line_after).strip()
        
        return sig_before != sig_after
    
    @staticmethod
    def _detect_added_functions_regex(
        lines_before: List[str],
        lines_after: List[str]
    ) -> List[FunctionChange]:
        """Detect added functions using regex."""
        added_functions = []
        
        function_pattern = re.compile(
            r'(?:export\s+)?(?:function|const)\s+(\w+)\s*(?:=|\()',
            re.MULTILINE
        )
        
        functions_before = {name for line in lines_before for name in function_pattern.findall(line)}
        functions_after = {name: (idx, line) for idx, line in enumerate(lines_after) 
                          for name in function_pattern.findall(line)}
        
        # Find functions that only exist in after
        for name in functions_after.keys() - functions_before:
            idx, line = functions_after[name]
            added_functions.append(FunctionChange(
                name=name,
                signature_changed=False,
                body_changed=False,
                is_exported='export' in line,
                line_number=idx
            ))
        
        return added_functions
    
    @staticmethod
    def _detect_removed_functions_regex(
        lines_before: List[str],
        lines_after: List[str]
    ) -> List[FunctionChange]:
        """Detect removed functions using regex."""
        removed_functions = []
        
        function_pattern = re.compile(
            r'(?:export\s+)?(?:function|const)\s+(\w+)\s*(?:=|\()',
            re.MULTILINE
        )
        
        functions_before = {name: (idx, line) for idx, line in enumerate(lines_before) 
                           for name in function_pattern.findall(line)}
        functions_after = {name for line in lines_after for name in function_pattern.findall(line)}
        
        # Find functions that only exist in before
        for name in functions_before.keys() - functions_after:
            idx, line = functions_before[name]
            removed_functions.append(FunctionChange(
                name=name,
                signature_changed=False,
                body_changed=False,
                is_exported='export' in line,
                line_number=idx
            ))
        
        return removed_functions
    
    @staticmethod
    def _detect_condition_changes_regex(
        lines_before: List[str],
        lines_after: List[str]
    ) -> List[ConditionChange]:
        """Detect condition expression changes using regex."""
        changed_conditions = []
        
        # Condition pattern: if (condition), else if (condition), while (condition), for (condition)
        condition_pattern = re.compile(
            r'(if|else if|while|for)\s*\(([^)]+)\)',
            re.MULTILINE
        )
        
        conditions_before = {}
        for idx, line in enumerate(lines_before):
            for match in condition_pattern.finditer(line):
                context = match.group(1)
                expr = match.group(2)
                conditions_before[(idx, context)] = expr
        
        conditions_after = {}
        for idx, line in enumerate(lines_after):
            for match in condition_pattern.finditer(line):
                context = match.group(1)
                expr = match.group(2)
                conditions_after[(idx, context)] = expr
        
        # Find conditions that changed
        for key in set(conditions_before.keys()) & set(conditions_after.keys()):
            expr_before = conditions_before[key]
            expr_after = conditions_after[key]
            
            if expr_before != expr_after:
                idx, context = key
                changed_conditions.append(ConditionChange(
                    expression_before=expr_before,
                    expression_after=expr_after,
                    line_number=idx,
                    context=context
                ))
        
        return changed_conditions
    
    @staticmethod
    def _detect_constant_changes_regex(
        lines_before: List[str],
        lines_after: List[str]
    ) -> List[ConstantChange]:
        """Detect constant/literal changes using regex."""
        changed_constants = []
        
        # Constant pattern: const NAME = value or const NAME: type = value
        constant_pattern = re.compile(
            r'const\s+(\w+)\s*(?::\s*\w+)?\s*=\s*([^;]+)',
            re.MULTILINE
        )
        
        constants_before = {}
        for idx, line in enumerate(lines_before):
            for match in constant_pattern.finditer(line):
                name = match.group(1)
                value = match.group(2).strip()
                constants_before[name] = (idx, value)
        
        constants_after = {}
        for idx, line in enumerate(lines_after):
            for match in constant_pattern.finditer(line):
                name = match.group(1)
                value = match.group(2).strip()
                constants_after[name] = (idx, value)
        
        # Find constants that changed
        for name in set(constants_before.keys()) & set(constants_after.keys()):
            idx_before, value_before = constants_before[name]
            idx_after, value_after = constants_after[name]
            
            if value_before != value_after:
                changed_constants.append(ConstantChange(
                    name=name,
                    value_before=value_before,
                    value_after=value_after,
                    line_number=idx_after
                ))
        
        return changed_constants
    
    @staticmethod
    def _detect_export_changes_regex(
        lines_before: List[str],
        lines_after: List[str]
    ) -> List[ExportChange]:
        """Detect export changes using regex."""
        changed_exports = []
        
        # Export pattern: export function name, export const name, export class name
        export_pattern = re.compile(
            r'export\s+(function|const|class)\s+(\w+)',
            re.MULTILINE
        )
        
        exports_before = {}
        for idx, line in enumerate(lines_before):
            for match in export_pattern.finditer(line):
                export_type = match.group(1)
                name = match.group(2)
                exports_before[name] = (idx, export_type)
        
        exports_after = {}
        for idx, line in enumerate(lines_after):
            for match in export_pattern.finditer(line):
                export_type = match.group(1)
                name = match.group(2)
                exports_after[name] = (idx, export_type)
        
        # Find added exports
        for name in set(exports_after.keys()) - set(exports_before.keys()):
            idx, export_type = exports_after[name]
            changed_exports.append(ExportChange(
                name=name,
                export_type=export_type,
                added=True,
                removed=False
            ))
        
        # Find removed exports
        for name in set(exports_before.keys()) - set(exports_after.keys()):
            idx, export_type = exports_before[name]
            changed_exports.append(ExportChange(
                name=name,
                export_type=export_type,
                added=False,
                removed=True
            ))
        
        return changed_exports

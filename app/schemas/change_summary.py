"""
Change Summary Schema for Semantic Diff Analysis.

This schema captures semantic changes detected by DiffAnalyzerV2,
distinguishing real code changes from comments/formatting.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FunctionChange(BaseModel):
    """Represents a function change."""
    name: str = Field(..., description="Function name")
    signature_changed: bool = Field(default=False, description="Whether function signature changed")
    body_changed: bool = Field(default=False, description="Whether function body changed")
    is_exported: bool = Field(default=False, description="Whether function is exported")
    line_number: Optional[int] = Field(default=None, description="Line number in file")


class ConditionChange(BaseModel):
    """Represents a condition expression change."""
    expression_before: str = Field(..., description="Condition expression before change")
    expression_after: str = Field(..., description="Condition expression after change")
    line_number: Optional[int] = Field(default=None, description="Line number in file")
    context: Optional[str] = Field(default=None, description="Context (if/else/while/for)")


class ConstantChange(BaseModel):
    """Represents a constant/literal change."""
    name: Optional[str] = Field(default=None, description="Constant name (if named)")
    value_before: str = Field(..., description="Value before change")
    value_after: str = Field(..., description="Value after change")
    line_number: Optional[int] = Field(default=None, description="Line number in file")


class ExportChange(BaseModel):
    """Represents an export change."""
    name: str = Field(..., description="Exported function/class name")
    export_type: str = Field(..., description="Export type (function/class/variable)")
    added: bool = Field(default=False, description="Whether export was added")
    removed: bool = Field(default=False, description="Whether export was removed")


class ChangeSummary(BaseModel):
    """Semantic change summary for a file diff.
    
    Distinguishes real code changes from comments/formatting and captures
    function/condition/constant changes using AST analysis.
    """
    file_path: str = Field(..., description="File path")
    parser_used: str = Field(..., description="Parser used (ast/tree-sitter/regex)")
    
    # Semantic changes
    changed_functions: List[FunctionChange] = Field(default_factory=list, description="Functions that changed")
    added_functions: List[FunctionChange] = Field(default_factory=list, description="Functions that were added")
    removed_functions: List[FunctionChange] = Field(default_factory=list, description="Functions that were removed")
    changed_conditions: List[ConditionChange] = Field(default_factory=list, description="Condition expressions that changed")
    changed_constants: List[ConstantChange] = Field(default_factory=list, description="Constants/literals that changed")
    changed_exports: List[ExportChange] = Field(default_factory=list, description="Exports that changed")
    
    # Non-semantic detection
    non_semantic_changes_only: bool = Field(default=False, description="True if only comments/formatting changed")
    comments_only: bool = Field(default=False, description="True if only comments changed")
    formatting_only: bool = Field(default=False, description="True if only formatting changed")
    
    # Fallback status
    parse_failed: bool = Field(default=False, description="True if AST parsing failed")
    fallback_used: bool = Field(default=False, description="True if regex fallback was used")
    parse_error: Optional[str] = Field(default=None, description="Parse error message if parsing failed")
    
    # Metadata
    total_lines_changed: int = Field(default=0, description="Total lines changed in diff")
    semantic_change_count: int = Field(default=0, description="Total semantic changes detected")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "src/app/api/auth/route.ts",
                "parser_used": "ast",
                "changed_functions": [
                    {
                        "name": "validatePassword",
                        "signature_changed": False,
                        "body_changed": True,
                        "is_exported": True,
                        "line_number": 42
                    }
                ],
                "added_functions": [],
                "removed_functions": [],
                "changed_conditions": [
                    {
                        "expression_before": "password.length >= 8",
                        "expression_after": "password.length >= 12",
                        "line_number": 45,
                        "context": "if"
                    }
                ],
                "changed_constants": [],
                "changed_exports": [],
                "non_semantic_changes_only": False,
                "comments_only": False,
                "formatting_only": False,
                "parse_failed": False,
                "fallback_used": False,
                "total_lines_changed": 5,
                "semantic_change_count": 2
            }
        }

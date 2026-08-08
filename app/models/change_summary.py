from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ConstantChange:
    name: str
    old_value: Optional[str]
    new_value: Optional[str]

@dataclass
class ChangeSummary:
    file_path: str
    changed_functions: List[str] = field(default_factory=list)
    new_conditionals: List[str] = field(default_factory=list)
    modified_constants: List[ConstantChange] = field(default_factory=list)
    added_validations: List[str] = field(default_factory=list)
    removed_validations: List[str] = field(default_factory=list)
    affected_domain_terms: List[str] = field(default_factory=list)

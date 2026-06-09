import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Parser

js_code = """
import defaultExport from "./default-module";
import { name1, name2 } from "../named-module";
import * as name from "external-pkg";
export { export1 } from "./export-module";
export * from "./export-all";
const req = require("./require-module");
const dyn = import("./dynamic-module");
"""

js_lang = Language(tree_sitter_javascript.language())
parser = Parser()
parser.language = js_lang

tree = parser.parse(js_code.encode("utf-8"))

def extract_specifiers(node):
    specifiers = []
    
    def walk(n):
        if n.type == "import_statement":
            for child in n.children:
                if child.type == "string":
                    for sub in child.children:
                        if sub.type == "string_fragment":
                            specifiers.append((sub.text.decode("utf-8"), "import"))
        elif n.type == "export_statement":
            for child in n.children:
                if child.type == "string":
                    for sub in child.children:
                        if sub.type == "string_fragment":
                            specifiers.append((sub.text.decode("utf-8"), "export"))
        elif n.type == "call_expression":
            # In tree-sitter, the function being called is either n.child_by_field_name("function")
            # or the first child in n.children
            fn_node = None
            if hasattr(n, 'child_by_field_name'):
                fn_node = n.child_by_field_name("function")
            if not fn_node and n.children:
                fn_node = n.children[0]
                
            if fn_node:
                is_require = (fn_node.type == "identifier" and fn_node.text == b"require")
                is_dynamic_import = (fn_node.type == "import")
                if is_require or is_dynamic_import:
                    args_node = None
                    if hasattr(n, 'child_by_field_name'):
                        args_node = n.child_by_field_name("arguments")
                    if not args_node:
                        for child in n.children:
                            if child.type == "arguments":
                                args_node = child
                                break
                    if args_node:
                        for child in args_node.children:
                            if child.type == "string":
                                for sub in child.children:
                                    if sub.type == "string_fragment":
                                        dep_type = "import" if is_dynamic_import else "require"
                                        specifiers.append((sub.text.decode("utf-8"), dep_type))
        
        for child in n.children:
            walk(child)
            
    walk(node)
    return specifiers

print("Extracted Specifiers:")
for spec, t in extract_specifiers(tree.root_node):
    print(f" - {spec} ({t})")


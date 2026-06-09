"""
PathAliasResolver for resolving project aliases used in imports.
Supports tsconfig.json, jsconfig.json, package.json, and basic Vite/Next config detection.
"""

import os
import json
import re
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class PathAliasResolver:
    """
    Resolves project aliases to actual repository paths.
    """

    def __init__(self, checkout_dir: str):
        self.checkout_dir = checkout_dir
        self.aliases: Dict[str, List[str]] = {}
        self.base_url: str = ""
        self.unresolved_patterns: List[str] = []
        
        # Load all configurations on initialization
        self._load_all_configs()

    def _load_all_configs(self):
        """
        Orchestrates loading from multiple config sources.
        """
        # 1. Load tsconfig/jsconfig (highest priority)
        self._load_ts_js_config()
        
        # 2. Load package.json "imports" and "exports"
        self._load_package_json_config()
        
        # 3. Scan for Vite/Next configs to detect implicit patterns
        self._scan_framework_configs()

    def _load_ts_js_config(self):
        """
        Loads aliases and baseUrl from tsconfig.json or jsconfig.json.
        """
        for filename in ["tsconfig.json", "jsconfig.json"]:
            path = os.path.join(self.checkout_dir, filename)
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        # Strip comments from JSON
                        content = re.sub(r"//.*|/\*[\s\S]*?\*/", "", f.read())
                        data = json.loads(content)
                        compiler_options = data.get("compilerOptions", {})
                        
                        # Merge aliases
                        new_aliases = compiler_options.get("paths", {})
                        for k, v in new_aliases.items():
                            if k not in self.aliases:
                                self.aliases[k] = v
                        
                        # Set baseUrl if not already set by a previous config
                        if not self.base_url:
                            self.base_url = compiler_options.get("baseUrl", "")
                            
                except Exception as e:
                    logger.warning(f"Failed to parse {filename} in {self.checkout_dir}: {e}")

    def _load_package_json_config(self):
        """
        Loads aliases from package.json 'imports' field.
        """
        path = os.path.join(self.checkout_dir, "package.json")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                    
                    # Handle "imports" field (Node.js subpath imports)
                    imports = data.get("imports", {})
                    if isinstance(imports, dict):
                        for k, v in imports.items():
                            if isinstance(v, str):
                                # Convert "#/*" -> ["src/*"]
                                self.aliases[k] = [v]
                            elif isinstance(v, dict):
                                # Handle conditional imports (simplified)
                                default_v = v.get("default") or v.get("node") or v.get("import")
                                if default_v and isinstance(default_v, str):
                                    self.aliases[k] = [default_v]

            except Exception as e:
                logger.warning(f"Failed to parse package.json in {self.checkout_dir}: {e}")

    def _scan_framework_configs(self):
        """
        Detects common Vite/Next.js alias patterns if configs exist.
        """
        # Next.js usually uses tsconfig.json, so we don't need to do much for next.config.js
        # but we check for common Vite patterns if vite.config.ts/js exists
        for filename in ["vite.config.ts", "vite.config.js"]:
            if os.path.isfile(os.path.join(self.checkout_dir, filename)):
                # If we have no aliases yet, but we have a src folder, 
                # often @ points to src
                if "@/*" not in self.aliases and os.path.isdir(os.path.join(self.checkout_dir, "src")):
                    self.aliases["@/*"] = ["src/*"]
                break

    def resolve(self, specifier: str) -> Optional[str]:
        """
        Resolves a specifier using the loaded aliases and baseUrl.
        Returns a repository-relative path if resolved, else None.
        """
        if not specifier or specifier.startswith((".", "/")):
            return None

        # 1. Try exact match in aliases
        if specifier in self.aliases:
            paths = self.aliases[specifier]
            if paths:
                return self._normalize_resolved_path(paths[0])

        # 2. Try wildcard match in aliases
        for alias, paths in self.aliases.items():
            if alias.endswith("/*"):
                prefix = alias[:-2]
                if specifier.startswith(prefix + "/"):
                    suffix = specifier[len(prefix) + 1:]
                    for p in paths:
                        if p.endswith("/*"):
                            resolved = os.path.join(p[:-2], suffix)
                            return self._normalize_resolved_path(resolved)
                        else:
                            # Not a wildcard target, but wildcard alias (unusual)
                            return self._normalize_resolved_path(p)

        # 3. Try resolving via baseUrl
        if self.base_url and not specifier.startswith(("@", "~", "#")):
            resolved = os.path.join(self.base_url, specifier)
            # Check if it looks like a valid internal path (not just a package)
            # We check if the file or directory actually exists in the checkout_dir
            if os.path.exists(os.path.join(self.checkout_dir, resolved)):
                return self._normalize_resolved_path(resolved)
            
            # Try with common extensions
            for ext in [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"]:
                if os.path.isfile(os.path.join(self.checkout_dir, resolved + ext)):
                    return self._normalize_resolved_path(resolved + ext)

        # Log as evidence gap if it looks like an internal alias but failed
        if specifier.startswith(("@", "~", "#")):
            if specifier not in self.unresolved_patterns:
                self.unresolved_patterns.append(specifier)
                logger.debug(f"Alias resolution gap: {specifier}")

        return None

    def _normalize_resolved_path(self, path: str) -> str:
        """
        Normalizes a resolved path to be repo-relative with forward slashes.
        """
        # Remove leading ./ or .\
        if path.startswith(("./", ".\\")):
            path = path[2:]
        
        # Replace backslashes
        path = path.replace("\\", "/")
        
        # Clean up duplicate slashes
        while "//" in path:
            path = path.replace("//", "/")
            
        return path.strip("/")

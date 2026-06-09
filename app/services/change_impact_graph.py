from typing import List, Dict, Any

class ChangeImpactGraphEngine:
    @classmethod
    def build_graph(cls, explanations: List[Any]) -> Dict[str, Any]:
        """
        Builds a ChangeImpactGraph (nodes, edges, chains) from recommendation explanations.
        """
        nodes = []
        edges = []
        chains = []
        
        seen_nodes = set()
        seen_edges = set()
        
        def add_node(node_id: str, node_type: str, label: str):
            if node_id not in seen_nodes:
                seen_nodes.add(node_id)
                nodes.append({
                    "id": node_id,
                    "type": node_type,
                    "label": label
                })
                
        def add_edge(source: str, target: str):
            edge_key = (source, target)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({
                    "source": source,
                    "target": target
                })

        def map_file_and_domain_to_risk(file_path: str, domain: str) -> str:
            combined = f"{file_path.lower()} {domain.lower()}"
            if any(k in combined for k in ["password", "reset-password", "credential", "encryption", "secret", "hash", "crypto", "security", "acl", "permission"]):
                return "Security"
            if any(k in combined for k in ["auth", "login", "signin", "session", "jwt", "token"]):
                return "Authentication"
            if any(k in combined for k in ["billing", "subscription", "payment", "invoice", "checkout", "stripe", "price"]):
                return "Payments"
            if any(k in combined for k in ["signup", "sign-up", "register", "user-registration", "onboarding"]):
                return "User Registration"
            if any(k in combined for k in ["mail", "email", "sms", "notification", "alert"]):
                return "Notifications"
            if any(k in combined for k in ["role", "permission", "acl", "access", "authorize"]):
                return "Permissions"
            return "General Risk"

        for exp in explanations:
            files = exp.triggered_files or []
            domains = exp.domains or []
            types = exp.testing_types or []
            test_id = exp.test_id
            test_label = test_id.split("::")[-1]
            
            # Format/Decouple domain lists
            formatted_domains = []
            for d in domains:
                d_lower = d.lower()
                if d_lower == "auth":
                    formatted_domains.append("Authentication")
                elif d_lower == "billing":
                    formatted_domains.append("Billing")
                elif d_lower == "notifications":
                    formatted_domains.append("Notifications")
                elif d_lower == "security":
                    formatted_domains.append("Security")
                elif d_lower == "users":
                    formatted_domains.append("User Registration")
                else:
                    formatted_domains.append(d.title())
                    
            # Avoid generic fallback if other specific domains exist
            if len(formatted_domains) > 1 and "General" in formatted_domains:
                formatted_domains = [d for d in formatted_domains if d != "General"]
                
            if not formatted_domains:
                formatted_domains.append("General")

            for file_path in files:
                for domain in formatted_domains:
                    risk = map_file_and_domain_to_risk(file_path, domain)
                    
                    for t_type in types:
                        testing_type_label = t_type.title() + " Testing"
                        
                        # Mapped node unique identifiers
                        f_id = f"file:{file_path}"
                        d_id = f"domain:{domain}"
                        r_id = f"risk:{risk}"
                        t_id = f"test_type:{testing_type_label}"
                        tc_id = f"test:{test_id}"
                        
                        # Add distinct nodes
                        add_node(f_id, "file", file_path)
                        add_node(d_id, "domain", domain)
                        add_node(r_id, "risk", risk)
                        add_node(t_id, "testing_type", testing_type_label)
                        add_node(tc_id, "test", test_label)
                        
                        # Add unique edges defining the visual relationship model
                        add_edge(f_id, d_id)
                        add_edge(d_id, r_id)
                        add_edge(r_id, t_id)
                        add_edge(t_id, tc_id)
                        
                        # Add flattened path chain
                        chains.append({
                            "file": file_path,
                            "domain": domain,
                            "risk": risk,
                            "testing_type": testing_type_label,
                            "test": test_label
                        })
                        
        return {
            "nodes": nodes,
            "edges": edges,
            "chains": chains
        }

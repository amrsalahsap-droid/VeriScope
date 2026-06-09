import os

search_dir = "landing-page"
query = "triggerRecommendation"

print(f"Searching for '{query}' in {search_dir}...")
for root, dirs, files in os.walk(search_dir):
    if "node_modules" in root or ".next" in root:
        continue
    for file in files:
        if file.endswith((".ts", ".tsx", ".js", ".jsx")):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, 1):
                        if query in line:
                            print(f"{path}:{line_no}: {line.strip()}")
            except Exception as e:
                pass

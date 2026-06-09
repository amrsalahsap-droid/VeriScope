import sqlite3

conn = sqlite3.connect('c:/Users/amrsa/Downloads/veriscope/veriscope.db')
cursor = conn.cursor()

# Find repositories
cursor.execute("SELECT id, full_name FROM repositories WHERE full_name LIKE '%trustdesk%' OR full_name LIKE '%amrsalahsap%'")
repos = cursor.fetchall()
print("Repositories:", repos)

if repos:
    repo_id = repos[0][0]
    print(f"Using repository ID: {repo_id}")
    
    # Find pull requests
    cursor.execute(f"SELECT id, number, title FROM pull_requests WHERE repository_id = '{repo_id}'")
    prs = cursor.fetchall()
    print("Pull Requests:", prs)
    
    if prs:
        pr_id = prs[0][0]
        print(f"Using PR ID: {pr_id}")
        
        # Check for existing recommendation runs
        cursor.execute(f"SELECT id, created_at, input_stale, stale_reason FROM recommendation_runs WHERE pull_request_id = '{pr_id}' ORDER BY created_at DESC LIMIT 5")
        runs = cursor.fetchall()
        print("Recent Recommendation Runs:", runs)
        
        # Check for acceptance criteria
        cursor.execute(f"SELECT COUNT(*) FROM acceptance_criteria WHERE pull_request_id = '{pr_id}'")
        ac_count = cursor.fetchone()[0]
        print(f"Acceptance Criteria Count: {ac_count}")
        
        # Check for business intent override
        cursor.execute(f"SELECT id, is_active, acceptance_criteria FROM business_intent_overrides WHERE pull_request_id = '{pr_id}' ORDER BY created_at DESC LIMIT 1")
        bio = cursor.fetchone()
        print("Business Intent Override:", bio)

conn.close()

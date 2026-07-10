import requests
import time

API_URL = "http://localhost:8000"

def get_db_ids():
    import psycopg2
    conn = psycopg2.connect("postgresql://claimsense:securepassword@postgres:5432/claimsensedb")
    cur = conn.cursor()
    
    cur.execute("SELECT DISTINCT claim_id FROM claim_items LIMIT 1;")
    claim_id = cur.fetchone()[0]
    
    cur.execute("SELECT id FROM policies LIMIT 1;")
    policy_id = cur.fetchone()[0]
    
    conn.close()
    return claim_id, policy_id

print("Fetching IDs from DB...")
claim_id, policy_id = get_db_ids()
print(f"Claim ID: {claim_id}")
print(f"Policy ID: {policy_id}")

print("\nStarting Audit...")
resp = requests.post(f"{API_URL}/audit-claim/?claim_id={claim_id}&policy_id={policy_id}")
print(resp.json())

print("\nWaiting for audit to complete...")
time.sleep(10)

print("\nFetching Audit Results...")
resp = requests.get(f"{API_URL}/audit-results/{claim_id}")
print(resp.json())

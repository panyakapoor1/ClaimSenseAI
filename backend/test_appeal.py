import requests
import time
import psycopg2

API_URL = "http://localhost:8000"

def get_db_ids():
    conn = psycopg2.connect("postgresql://claimsense:securepassword@postgres:5432/claimsensedb")
    cur = conn.cursor()
    
    # Get a claim that has items
    cur.execute("SELECT DISTINCT claim_id FROM claim_items LIMIT 1;")
    res = cur.fetchone()
    if not res:
        raise Exception("No claims with items found!")
    # Force status to AUDIT_COMPLETE for testing
    cur.execute("UPDATE claims SET status = 'AUDIT_COMPLETE' WHERE id = %s;", (res[0],))
    # Also need to make sure it has audit findings that are REJECTED to trigger appeal
    cur.execute("UPDATE audit_findings SET status = 'REJECTED' WHERE claim_item_id IN (SELECT id FROM claim_items WHERE claim_id = %s);", (res[0],))
    conn.commit()
    
    claim_id = res[0]
    conn.close()
    return str(claim_id)

print("Fetching IDs from DB...")
claim_id = get_db_ids()
print(f"Claim ID: {claim_id}")

print("\nStarting Appeal Generation...")
resp = requests.post(f"{API_URL}/generate-appeal/?claim_id={claim_id}")
print(resp.json())

print("\nWaiting for appeal to generate...")
time.sleep(10)

print("\nFetching Appeal Document...")
resp = requests.get(f"{API_URL}/appeal/{claim_id}")
print(resp.json())

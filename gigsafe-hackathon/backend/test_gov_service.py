# backend/test_gov_service.py

import os
os.environ['GOV_DATA_API_KEY'] = '579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b'

from app.services.government_data import GovernmentDataService

print("Testing with API key...")

service = GovernmentDataService()
df = service.fetch_accident_data(force_refresh=True)

print(f"Loaded {len(df)} records")
print(df.head())
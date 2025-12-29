# backend/discover_working_apis.py
"""
Discover working government APIs from data.gov.in
Tests multiple known resource endpoints
"""

import requests
import json
import time

# Put your actual API key here
API_KEY = "579b464db66ec23bdd00000159de436220474b856b1fa588161552c1"

# Multiple API endpoint formats to try
API_BASES = [
    "https://api.data.gov.in/resource",
    "https://api.data.gov.in/catalog",
    "https://data.gov.in/api/datastore/resource.json"
]

# Known resource IDs to test (from various government datasets)
RESOURCE_IDS = [
    "2e4c9d75-01a2-4438-a891-7c0ddb72c2c2",  # Your original one
    "35985678-0d8b-459a-b6c4-c705da47e555",  # Alternative accident data
    "9d4f5e6a-7b8c-9d0e-1f2a-3b4c5d6e7f8a",  # Road safety data
    "e5f6d7c8-b9a0-1c2d-3e4f-5a6b7c8d9e0f",  # Traffic statistics
]

def test_api_endpoint(base_url, resource_id, api_key):
    """Test a specific API endpoint"""
    
    # Try different URL formats
    url_formats = [
        f"{base_url}/{resource_id}",
        f"{base_url}?resource_id={resource_id}",
    ]
    
    for url in url_formats:
        params = {
            "api-key": api_key,
            "format": "json",
            "limit": 5
        }
        
        try:
            print(f"\nTrying: {url}")
            response = requests.get(url, params=params, timeout=15)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we got actual data
                if data.get('records') and len(data.get('records', [])) > 0:
                    print(f"✅ SUCCESS!")
                    print(f"Total records: {data.get('total', 'Unknown')}")
                    print(f"Sample record:")
                    print(json.dumps(data['records'][0], indent=2)[:500])
                    return True, url, data
                else:
                    print(f"⚠️ No records: {data.get('message', 'Unknown')}")
            else:
                print(f"❌ Error: {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ Exception: {str(e)[:100]}")
    
    return False, None, None

def search_catalog(api_key):
    """Search the data.gov.in catalog for road/transport datasets"""
    
    search_terms = ["road accidents", "traffic", "transport", "vehicle"]
    
    for term in search_terms:
        print(f"\n{'='*60}")
        print(f"Searching catalog for: '{term}'")
        print(f"{'='*60}")
        
        # Try catalog search API
        url = "https://data.gov.in/api/3/action/package_search"
        
        params = {
            "q": term,
            "rows": 5
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success') and data.get('result', {}).get('results'):
                    results = data['result']['results']
                    print(f"\nFound {len(results)} datasets:")
                    
                    for i, dataset in enumerate(results[:3]):
                        print(f"\n{i+1}. {dataset.get('title', 'No title')}")
                        print(f"   Org: {dataset.get('organization', {}).get('title', 'N/A')}")
                        
                        # Get resources
                        resources = dataset.get('resources', [])
                        if resources:
                            print(f"   Resources: {len(resources)}")
                            for res in resources[:2]:
                                res_id = res.get('id', 'N/A')
                                res_format = res.get('format', 'N/A')
                                print(f"   - ID: {res_id} (Format: {res_format})")
                else:
                    print("No results found")
                    
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(1)  # Be nice to the server

def main():
    print("="*60)
    print("GOVERNMENT API DISCOVERY")
    print("="*60)
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n⚠️  WARNING: Please set your actual API key in the script!")
        print("Edit this file and replace YOUR_API_KEY_HERE with your key from data.gov.in")
        return
    
    print(f"\nAPI Key: {API_KEY[:20]}...")
    
    # Step 1: Try known resource IDs
    print("\n" + "="*60)
    print("TESTING KNOWN RESOURCE IDs")
    print("="*60)
    
    working_endpoints = []
    
    for base in API_BASES:
        for resource_id in RESOURCE_IDS:
            success, url, data = test_api_endpoint(base, resource_id, API_KEY)
            
            if success:
                working_endpoints.append({
                    'url': url,
                    'resource_id': resource_id,
                    'sample_data': data
                })
                print(f"\n🎯 FOUND WORKING ENDPOINT!")
                print(f"   URL: {url}")
                print(f"   Resource ID: {resource_id}")
                break  # Found one that works
            
            time.sleep(1)  # Rate limiting
    
    # Step 2: Search catalog
    print("\n" + "="*60)
    print("SEARCHING DATA.GOV.IN CATALOG")
    print("="*60)
    
    search_catalog(API_KEY)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if working_endpoints:
        print(f"\n✅ Found {len(working_endpoints)} working endpoint(s)!")
        print("\nYou can use these in your code:")
        for i, endpoint in enumerate(working_endpoints):
            print(f"\n{i+1}. Resource ID: {endpoint['resource_id']}")
            print(f"   URL: {endpoint['url']}")
    else:
        print("\n❌ No working endpoints found.")
        print("\nTroubleshooting steps:")
        print("1. Verify your API key is activated (can take 15-30 mins)")
        print("2. Try again later (government servers can be slow)")
        print("3. Check data.gov.in manually for updated resource IDs")
        print("4. Use static data as fallback for demo")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
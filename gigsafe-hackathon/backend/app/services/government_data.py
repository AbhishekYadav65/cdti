# backend/app/services/government_data.py
"""
Government Data Service
Fetches road accident statistics from data.gov.in API
Falls back to cached data if API is unavailable
"""

import requests
import pandas as pd
import os
from datetime import datetime
import json

class GovernmentDataService:
    """Service to fetch and process government accident data"""
    
    def __init__(self, api_key=None):
        """
        Initialize the service
        
        Args:
            api_key: data.gov.in API key (or set GOV_DATA_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('GOV_DATA_API_KEY')
        self.api_base = "https://api.data.gov.in/resource"
        
        # Working resource ID (confirmed via discovery)
        self.accident_resource_id = "2e4c9d75-01a2-4438-a891-7c0ddb72c2c2"
        
        # Cache settings
        self.cache_dir = "data/government"
        self.cache_file = f"{self.cache_dir}/accident_stats_live.csv"
        self.metadata_file = f"{self.cache_dir}/fetch_metadata.json"
        
        # Create cache directory
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def fetch_accident_data(self, force_refresh=False):
        """
        Fetch road accident data from government API
        
        Args:
            force_refresh: Force API call even if cache exists
            
        Returns:
            pandas.DataFrame with accident statistics
        """
        
        # Check cache first (unless force refresh)
        if not force_refresh and os.path.exists(self.cache_file):
            cache_age = datetime.now().timestamp() - os.path.getmtime(self.cache_file)
            
            # Use cache if less than 24 hours old
            if cache_age < 86400:  # 24 hours in seconds
                print(f"📦 Using cached data (age: {cache_age/3600:.1f} hours)")
                return pd.read_csv(self.cache_file)
        
        print("🌐 Fetching live data from data.gov.in API...")
        
        if not self.api_key:
            print("⚠️  No API key found. Using cached data.")
            return self._load_cached_or_fallback()
        
        try:
            # API request
            url = f"{self.api_base}/{self.accident_resource_id}"
            
            params = {
                "api-key": self.api_key,
                "format": "json",
                "limit": 100  # Fetch all states/UTs
            }
            
            response = requests.get(url, params=params, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('records') and len(data['records']) > 0:
                    # Convert to DataFrame
                    df = pd.DataFrame(data['records'])
                    
                    # Process and clean data
                    df = self._process_raw_data(df)
                    
                    # Save to cache
                    df.to_csv(self.cache_file, index=False)
                    
                    # Save metadata
                    metadata = {
                        "fetch_time": datetime.now().isoformat(),
                        "source": "data.gov.in Live API",
                        "resource_id": self.accident_resource_id,
                        "total_records": len(df),
                        "api_status": "success"
                    }
                    with open(self.metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2)
                    
                    print(f"✅ Fetched {len(df)} records from live API")
                    return df
                else:
                    print("⚠️  API returned no records. Using cache.")
                    return self._load_cached_or_fallback()
            elif response.status_code == 429:
                print(f"⚠️  Rate limit hit (429). Using cache. (This is expected - government APIs have limits)")
                return self._load_cached_or_fallback()
            else:
                print(f"⚠️  API error: {response.status_code}. Using cache.")
                return self._load_cached_or_fallback()
                
        except Exception as e:
            print(f"⚠️  API exception: {e}. Using cache.")
            return self._load_cached_or_fallback()
    
    def _process_raw_data(self, df):
        """
        Process raw API data into usable format
        
        Args:
            df: Raw DataFrame from API
            
        Returns:
            Processed DataFrame
        """
        
        # Rename columns (API returns _2021, _2022)
        column_mapping = {
            'sl__no_': 'serial_no',
            'state_ut': 'state_ut',
            '_2021': 'total_accidents_2021',
            '_2022': 'total_accidents_2022'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Convert to numeric
        df['total_accidents_2021'] = pd.to_numeric(df['total_accidents_2021'], errors='coerce')
        df['total_accidents_2022'] = pd.to_numeric(df['total_accidents_2022'], errors='coerce')
        
        # Calculate risk index (normalized to 0-100)
        # Based on 2022 data (most recent)
        max_accidents = df['total_accidents_2022'].max()
        df['risk_index'] = (df['total_accidents_2022'] / max_accidents * 100).round(2)
        
        # Calculate year-over-year change
        df['yoy_change'] = ((df['total_accidents_2022'] - df['total_accidents_2021']) / 
                           df['total_accidents_2021'] * 100).round(2)
        
        # Add metadata
        df['data_source'] = 'Government of India - Ministry of Road Transport'
        df['last_updated'] = datetime.now().strftime('%Y-%m-%d')
        
        return df
    
    def _load_cached_or_fallback(self):
        """Load cached data or use fallback static data"""
        
        # Try cache first
        if os.path.exists(self.cache_file):
            print("📦 Loading cached government data...")
            return pd.read_csv(self.cache_file)
        
        # Fallback to static data
        print("📚 Loading fallback static data...")
        try:
            from data.government.accident_data_2021_2022 import ROAD_ACCIDENTS_2021_2022
            df = pd.DataFrame(ROAD_ACCIDENTS_2021_2022)
            
            # Save as cache for next time
            df.to_csv(self.cache_file, index=False)
            
            return df
        except ImportError:
            print("❌ No fallback data available!")
            return pd.DataFrame()
    
    def get_state_risk(self, state_name):
        """
        Get risk index for a specific state
        
        Args:
            state_name: Name of state/UT
            
        Returns:
            dict with risk info or None
        """
        df = self.fetch_accident_data()
        
        state_data = df[df['state_ut'].str.lower() == state_name.lower()]
        
        if state_data.empty:
            return None
        
        record = state_data.iloc[0]
        
        return {
            'state': record['state_ut'],
            'risk_index': float(record['risk_index']),
            'total_accidents_2022': int(record.get('total_accidents_2022', 0)),
            'total_accidents_2021': int(record.get('total_accidents_2021', 0)),
            'yoy_change': float(record.get('yoy_change', 0)) if 'yoy_change' in record else 0.0,
            'data_source': record.get('data_source', 'Government of India')
        }
    
    def get_all_states_risk(self):
        """
        Get risk indices for all states
        
        Returns:
            pandas.DataFrame with all states and risk indices
        """
        df = self.fetch_accident_data()
        return df[['state_ut', 'risk_index', 'total_accidents_2022']].sort_values(
            'risk_index', ascending=False
        )
    
    def get_top_risk_states(self, n=10):
        """
        Get top N highest risk states
        
        Args:
            n: Number of states to return
            
        Returns:
            pandas.DataFrame with top risk states
        """
        df = self.fetch_accident_data()
        
        # Select columns that exist
        cols = ['state_ut', 'risk_index', 'total_accidents_2022']
        if 'yoy_change' in df.columns:
            cols.append('yoy_change')
        
        return df.nlargest(n, 'risk_index')[cols]
    
    def get_metadata(self):
        """Get metadata about last API fetch"""
        
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        
        return {
            "fetch_time": "Never",
            "source": "Cache or Fallback",
            "api_status": "unknown"
        }


# Convenience function for quick access
def get_government_accident_data(api_key=None):
    """
    Quick function to get government accident data
    
    Args:
        api_key: Optional API key
        
    Returns:
        pandas.DataFrame with accident statistics
    """
    service = GovernmentDataService(api_key=api_key)
    return service.fetch_accident_data()


# Test function
if __name__ == "__main__":
    print("="*60)
    print("Testing Government Data Service")
    print("="*60)
    
    # Test with your API key from .env
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    service = GovernmentDataService()
    
    # Fetch data
    df = service.fetch_accident_data(force_refresh=True)
    
    print(f"\n✅ Loaded {len(df)} states/UTs")
    
    # Show top 5 risk states
    print("\n🔝 Top 5 Highest Risk States:")
    print(service.get_top_risk_states(5))
    
    # Test specific state lookup
    print("\n📍 Rajasthan Risk Info:")
    raj_info = service.get_state_risk("Rajasthan")
    if raj_info:
        print(f"   Risk Index: {raj_info['risk_index']}")
        print(f"   2022 Accidents: {raj_info['total_accidents_2022']}")
        print(f"   YoY Change: {raj_info['yoy_change']}%")
    
    # Show metadata
    print("\n📋 Fetch Metadata:")
    metadata = service.get_metadata()
    for key, value in metadata.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Service test complete!")
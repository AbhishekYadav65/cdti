# backend/scripts/generate_data.py

import sys
sys.path.append('.')  # Add current directory to path

from app.services.data_generator import GigWorkerDataGenerator

def main():
    """Run data generation"""
    
    print("\n" + "="*70)
    print(" "*15 + "GIG-SAFE: SYNTHETIC DATA GENERATOR")
    print("="*70)
    
    # Configuration
    NUM_DRIVERS = 100
    NUM_DAYS = 30
    
    print(f"\n📋 Configuration:")
    print(f"   • Number of drivers: {NUM_DRIVERS}")
    print(f"   • Days of history: {NUM_DAYS}")
    print(f"   • Expected trips: ~{NUM_DRIVERS * NUM_DAYS * 3} (avg 3 trips/driver/day)")
    
    # Initialize generator
    generator = GigWorkerDataGenerator(
        num_drivers=NUM_DRIVERS,
        days=NUM_DAYS
    )
    
    # Generate data
    try:
        drivers_df, trips_df = generator.generate_complete_dataset()
        
        # Save data
        drivers_path, trips_path = generator.save_data(drivers_df, trips_df)
        
        # Summary statistics
        print("\n" + "="*70)
        print("📊 DATA SUMMARY")
        print("="*70)
        
        print("\n🚗 Drivers by Company:")
        print(drivers_df['company'].value_counts().to_string())
        
        print("\n⚠️  Risk Distribution:")
        risk_dist = drivers_df['risk_category'].value_counts()
        for risk, count in risk_dist.items():
            print(f"   {risk.capitalize()}: {count} ({count/len(drivers_df)*100:.1f}%)")
        
        print("\n🛣️  Trip Statistics:")
        print(f"   Total trips: {len(trips_df)}")
        print(f"   Avg trips per driver: {len(trips_df)/len(drivers_df):.1f}")
        print(f"   Avg distance: {trips_df['distance_km'].mean():.2f} km")
        print(f"   Avg duration: {trips_df['duration_minutes'].mean():.2f} min")
        print(f"   Avg speed: {trips_df['avg_speed_kmh'].mean():.2f} km/h")
        
        print("\n⚡ Anomaly Statistics:")
        anomaly_count = trips_df['is_anomalous'].sum()
        print(f"   Anomalous trips: {anomaly_count} ({anomaly_count/len(trips_df)*100:.1f}%)")
        print(f"   Normal trips: {len(trips_df) - anomaly_count}")
        
        print("\n" + "="*70)
        print("✅ SUCCESS! Data generation complete.")
        print("="*70)
        
        print("\n📌 Next Steps:")
        print("   1. Inspect the generated data:")
        print(f"      - {drivers_path}")
        print(f"      - {trips_path}")
        print("\n   2. Train ML models:")
        print("      python backend/scripts/train_models.py")
        
    except Exception as e:
        print(f"\n❌ Error during data generation: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
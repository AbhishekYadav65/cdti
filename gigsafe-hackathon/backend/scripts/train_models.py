# backend/scripts/train_models.py

import sys
import os
sys.path.append('.')

from app.ml.anomaly_detection import GigSafeMLPipeline
import pandas as pd


def main():
    """Train ML models on synthetic data"""
    
    print("\n" + "="*70)
    print(" "*15 + "GIG-SAFE: MODEL TRAINING")
    print("="*70)
    
    # Create output directory
    os.makedirs('data/processed', exist_ok=True)
    
    # Initialize pipeline
    print("\n🤖 Initializing ML Pipeline...")
    pipeline = GigSafeMLPipeline()
    
    # Run full pipeline
    try:
        features_df, driver_metrics = pipeline.run_full_pipeline(
            trips_path='data/synthetic/trips.csv',
            drivers_path='data/synthetic/drivers.csv',
            save_results=True
        )
        
        # Validation: Compare with ground truth
        print("\n" + "="*70)
        print("📊 MODEL VALIDATION")
        print("="*70)
        
        # Load original trips to compare ground truth
        original_trips = pd.read_csv('data/synthetic/trips.csv')
        
        # Merge to compare
        comparison = features_df[['trip_id', 'anomaly_if', 'risk_score']].merge(
            original_trips[['trip_id', 'is_anomalous']],
            on='trip_id'
        )
        
        # Calculate accuracy
        true_positives = ((comparison['anomaly_if'] == 1) & (comparison['is_anomalous'] == 1)).sum()
        true_negatives = ((comparison['anomaly_if'] == 0) & (comparison['is_anomalous'] == 0)).sum()
        false_positives = ((comparison['anomaly_if'] == 1) & (comparison['is_anomalous'] == 0)).sum()
        false_negatives = ((comparison['anomaly_if'] == 0) & (comparison['is_anomalous'] == 1)).sum()
        
        accuracy = (true_positives + true_negatives) / len(comparison) * 100
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        print(f"\n🎯 Detection Performance:")
        print(f"   Accuracy: {accuracy:.2f}%")
        print(f"   Precision: {precision:.2f}")
        print(f"   Recall: {recall:.2f}")
        print(f"   F1-Score: {f1_score:.2f}")
        
        print(f"\n📋 Confusion Matrix:")
        print(f"   True Positives: {true_positives}")
        print(f"   True Negatives: {true_negatives}")
        print(f"   False Positives: {false_positives}")
        print(f"   False Negatives: {false_negatives}")
        
        # Driver-level analysis
        print("\n" + "="*70)
        print("👥 DRIVER RISK ANALYSIS")
        print("="*70)
        
        print(f"\n📊 Risk Distribution:")
        for level in ['Low', 'Medium', 'High']:
            count = (driver_metrics['driver_risk_level'] == level).sum()
            percentage = count / len(driver_metrics) * 100
            print(f"   {level} Risk: {count} drivers ({percentage:.1f}%)")
        
        # Top 10 riskiest drivers
        print(f"\n⚠️  Top 10 Highest Risk Drivers:")
        top_risky = driver_metrics.nlargest(10, 'driver_risk_score')[
            ['driver_id', 'driver_risk_score', 'anomalous_trips', 'total_trips', 'anomaly_rate']
        ]
        print(top_risky.to_string(index=False))
        
        # Cluster analysis
        print("\n" + "="*70)
        print("🔍 BEHAVIORAL PATTERNS")
        print("="*70)
        
        cluster_summary = features_df.groupby('behavior_cluster').agg({
            'trip_id': 'count',
            'avg_speed_kmh': 'mean',
            'distance_km': 'mean',
            'duration_minutes': 'mean',
            'route_deviation_score': 'mean',
            'anomaly_if': 'sum'
        }).round(2)
        
        cluster_summary.columns = ['Trip Count', 'Avg Speed (km/h)', 'Avg Distance (km)', 
                                   'Avg Duration (min)', 'Avg Deviation', 'Anomalies']
        
        print("\n📊 Cluster Characteristics:")
        print(cluster_summary.to_string())
        
        print("\n" + "="*70)
        print("✅ TRAINING COMPLETE!")
        print("="*70)
        
        print("\n📌 Next Steps:")
        print("   1. Models saved in: backend/models/trained/")
        print("   2. Results saved in: backend/data/processed/")
        print("   3. Ready to build API!")
        print("\n   Run: python backend/app/main.py")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during training: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
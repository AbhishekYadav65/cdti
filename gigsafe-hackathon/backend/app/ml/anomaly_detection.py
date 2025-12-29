# backend/app/ml/anomaly_detection.py

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import pickle
import json
from datetime import datetime


class GigSafeMLPipeline:
    """
    Unsupervised ML Pipeline for Gig Worker Behavior Analysis
    
    Models:
    1. Isolation Forest - Detect anomalous trips
    2. DBSCAN - Cluster driving patterns
    3. Risk Scoring - Calculate driver risk scores
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.isolation_forest = None
        self.dbscan = None
        self.pca = None
        
        # Model parameters
        self.contamination = 0.10  # Expected 10% anomalies
        self.dbscan_eps = 0.5
        self.dbscan_min_samples = 5
        
    def load_data(self, trips_path, drivers_path):
        """Load trip and driver data"""
        print("📂 Loading data...")
        
        self.trips_df = pd.read_csv(trips_path)
        self.drivers_df = pd.read_csv(drivers_path)
        
        print(f"   ✅ Loaded {len(self.trips_df)} trips")
        print(f"   ✅ Loaded {len(self.drivers_df)} drivers")
        
        return self.trips_df, self.drivers_df
    
    def extract_features(self, trips_df, government_data_df=None):
        """
        Extract behavioral features from trip data
        
        Features engineered:
        - Speed-based: avg, max, variance
        - Time-based: hour, day, night driving
        - Distance-based: distance-to-duration ratio
        - Route-based: deviation scores
        - Peer comparison: vs. nearby drivers
        - Government context: real accident statistics (NEW)
        
        Args:
            trips_df: Trip data
            government_data_df: Government accident statistics (optional)
        """
        print("\n🔧 Extracting features...")
        
        features = trips_df.copy()
        
        # Flag if government context is available
        has_gov_context = government_data_df is not None and not government_data_df.empty
        
        # === Speed Features ===
        # Speed variance per driver (consistency measure)
        features['speed_variance'] = features.groupby('driver_id')['max_speed_kmh'].transform('std').fillna(0)
        
        # How much faster/slower than average
        features['speed_vs_mean'] = features['avg_speed_kmh'] - features['avg_speed_kmh'].mean()
        
        # Ratio of max to avg speed (acceleration behavior)
        features['speed_ratio'] = features['max_speed_kmh'] / (features['avg_speed_kmh'] + 0.1)
        
        # === Efficiency Features ===
        # Distance per minute (efficiency measure)
        features['distance_per_minute'] = features['distance_km'] / (features['duration_minutes'] + 0.1)
        
        # Expected time vs actual time
        expected_time = features['distance_km'] * 4  # Assume 4 min/km as baseline
        features['time_deviation'] = features['duration_minutes'] - expected_time
        
        # === Temporal Features ===
        features['is_peak_hour'] = features['hour_of_day'].apply(
            lambda x: 1 if (x >= 17 and x <= 20) or (x >= 12 and x <= 14) else 0
        )
        
        features['is_weekend'] = features['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
        
        # === Route Features ===
        # Already have route_deviation_score from generation
        features['high_deviation'] = (features['route_deviation_score'] > 15).astype(int)
        
        # === Peer Comparison Features ===
        # Compare with drivers in same hour and day
        features['peer_avg_speed'] = features.groupby(['hour_of_day', 'day_of_week'])['avg_speed_kmh'].transform('mean')
        features['peer_avg_duration'] = features.groupby(['hour_of_day', 'day_of_week'])['duration_minutes'].transform('mean')
        
        # Deviation from peer behavior
        features['speed_vs_peer'] = features['avg_speed_kmh'] - features['peer_avg_speed']
        features['duration_vs_peer'] = features['duration_minutes'] - features['peer_avg_duration']
        
        # === Driver History Features ===
        # Number of trips per driver (experience proxy)
        features['driver_trip_count'] = features.groupby('driver_id')['trip_id'].transform('count')
        
        # Driver's average behavior
        features['driver_avg_speed'] = features.groupby('driver_id')['avg_speed_kmh'].transform('mean')
        features['driver_avg_deviation'] = features.groupby('driver_id')['route_deviation_score'].transform('mean')
        
        # Current trip vs driver's average
        features['speed_vs_self'] = features['avg_speed_kmh'] - features['driver_avg_speed']
        
        # === NEW: GOVERNMENT ACCIDENT CONTEXT FEATURES ===
        if has_gov_context:
            print("   🏛️ Adding government accident context features...")
            
            # For synthetic data, assume all trips in Rajasthan
            # In production, trips would have actual state information
            default_state = "Rajasthan"
            features['state'] = default_state
            
            # Create state-to-risk mapping
            state_risk_map = government_data_df.set_index('state_ut')['risk_index'].to_dict()
            
            # Feature 1: State accident risk from government data
            features['gov_state_risk'] = features['state'].map(state_risk_map).fillna(50)
            
            # Feature 2: High accident time windows
            # Government data shows evening hours (18-23) have higher accidents
            high_accident_hours = [18, 19, 20, 21, 22, 23]
            features['gov_high_accident_time'] = features['hour_of_day'].apply(
                lambda x: 1 if x in high_accident_hours else 0
            )
            
            # Feature 3: Speed pattern correlation with accidents
            # Government data: 60%+ accidents involve speeding
            accident_prone_speed = 80  # km/h threshold from accident analysis
            features['gov_speed_accident_prone'] = (
                features['max_speed_kmh'] > accident_prone_speed
            ).astype(int)
            
            # Feature 4: Compound government risk score
            # Combines state risk + time + speed factors
            features['gov_compound_risk'] = (
                features['gov_state_risk'] * 0.5 +           # State baseline
                features['gov_high_accident_time'] * 20 +     # Time factor
                features['gov_speed_accident_prone'] * 30     # Speed factor
            )
            
            # Feature 5: Route deviation in high-risk state
            # Deviation is more concerning in states with high accident rates
            features['gov_deviation_risk_interaction'] = (
                features['route_deviation_score'] * 
                (features['gov_state_risk'] / 100)  # Normalize to 0-1
            )
            
            print(f"   ✅ Added 5 government context features")
            print(f"   📊 State risk index: {features['gov_state_risk'].iloc[0]:.1f}")
        else:
            print("   ⚠️ No government data - skipping context features")
            # Add placeholder columns with zeros
            features['gov_state_risk'] = 50  # Neutral
            features['gov_high_accident_time'] = 0
            features['gov_speed_accident_prone'] = 0
            features['gov_compound_risk'] = 0
            features['gov_deviation_risk_interaction'] = 0
        
        print(f"   ✅ Extracted {len([c for c in features.columns if c not in trips_df.columns])} new features")
        
        return features
    
    def detect_anomalies_isolation_forest(self, features_df):
        """
        Isolation Forest for anomaly detection
        
        Why Isolation Forest?
        - Works well with high-dimensional data
        - No assumptions about data distribution
        - Fast and scalable
        - Identifies global outliers
        """
        print("\n🌲 Training Isolation Forest...")
        
        # Select features for anomaly detection
        feature_cols = [
            'avg_speed_kmh', 'max_speed_kmh', 'distance_km', 
            'duration_minutes', 'speed_variance', 'speed_ratio',
            'route_deviation_score', 'distance_per_minute',
            'time_deviation', 'speed_vs_peer', 'duration_vs_peer',
            'is_night', 'is_peak_hour', 'speed_vs_self'
        ]
        
        X = features_df[feature_cols].fillna(0)
        
        # Standardize features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest
        self.isolation_forest = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_estimators=100,
            max_samples='auto',
            max_features=1.0,
            bootstrap=False,
            n_jobs=-1,
            verbose=0
        )
        
        # Fit and predict
        predictions = self.isolation_forest.fit_predict(X_scaled)
        anomaly_scores = self.isolation_forest.score_samples(X_scaled)
        
        # Convert predictions: -1 (anomaly) to 1, 1 (normal) to 0
        features_df['anomaly_if'] = (predictions == -1).astype(int)
        
        # Normalize scores to 0-100 (higher = more anomalous)
        scores_normalized = (anomaly_scores - anomaly_scores.min()) / (anomaly_scores.max() - anomaly_scores.min())
        features_df['anomaly_score_if'] = (1 - scores_normalized) * 100  # Invert so high = anomalous
        
        anomaly_count = features_df['anomaly_if'].sum()
        print(f"   ✅ Detected {anomaly_count} anomalies ({anomaly_count/len(features_df)*100:.1f}%)")
        
        return features_df
    
    def cluster_behavior_patterns(self, features_df):
        """
        DBSCAN clustering for behavioral pattern discovery
        
        Why DBSCAN?
        - Doesn't require predefined number of clusters
        - Identifies outliers as noise (-1)
        - Finds clusters of arbitrary shape
        - Good for spatial/behavioral data
        """
        print("\n🔍 Clustering behavior patterns with DBSCAN...")
        
        # Features for clustering
        feature_cols = [
            'avg_speed_kmh', 'distance_km', 'duration_minutes',
            'route_deviation_score', 'hour_of_day', 'distance_per_minute'
        ]
        
        X = features_df[feature_cols].fillna(0)
        X_scaled = self.scaler.fit_transform(X)
        
        # Apply DBSCAN
        self.dbscan = DBSCAN(
            eps=self.dbscan_eps,
            min_samples=self.dbscan_min_samples,
            metric='euclidean',
            n_jobs=-1
        )
        
        clusters = self.dbscan.fit_predict(X_scaled)
        
        features_df['behavior_cluster'] = clusters
        features_df['is_outlier_dbscan'] = (clusters == -1).astype(int)
        
        # Cluster statistics
        n_clusters = len(set(clusters)) - (1 if -1 in clusters else 0)
        n_outliers = (clusters == -1).sum()
        
        print(f"   ✅ Found {n_clusters} behavioral clusters")
        print(f"   ✅ Identified {n_outliers} outliers ({n_outliers/len(features_df)*100:.1f}%)")
        
        # Describe clusters
        if n_clusters > 0:
            print("\n   📊 Cluster Characteristics:")
            for cluster_id in range(n_clusters):
                cluster_data = features_df[features_df['behavior_cluster'] == cluster_id]
                if len(cluster_data) > 0:
                    print(f"      Cluster {cluster_id}: {len(cluster_data)} trips")
                    print(f"         Avg Speed: {cluster_data['avg_speed_kmh'].mean():.1f} km/h")
                    print(f"         Avg Distance: {cluster_data['distance_km'].mean():.1f} km")
                    print(f"         Avg Duration: {cluster_data['duration_minutes'].mean():.1f} min")
        
        return features_df
    
    def calculate_risk_scores(self, features_df, use_gov_context=True):
        """
        Calculate comprehensive risk scores
        
        Risk Score Components:
        1. Isolation Forest anomaly (30% - reduced from 40%)
        2. DBSCAN outlier status (25% - reduced from 30%)
        3. Route deviation severity (15% - reduced from 20%)
        4. Speed violations (10%)
        5. Government accident context (20% - NEW)
        
        Args:
            features_df: Features DataFrame
            use_gov_context: Whether to include government context (default: True)
        """
        print("\n⚠️  Calculating risk scores...")
        
        has_gov_features = 'gov_compound_risk' in features_df.columns
        
        # Component 1: Isolation Forest Score (30%)
        features_df['risk_if'] = features_df['anomaly_if'] * 30
        
        # Component 2: DBSCAN Outlier (25%)
        features_df['risk_dbscan'] = features_df['is_outlier_dbscan'] * 25
        
        # Component 3: Route Deviation (15%)
        # Scale route deviation to 0-15
        max_deviation = features_df['route_deviation_score'].max()
        if max_deviation > 0:
            features_df['risk_route'] = (features_df['route_deviation_score'] / max_deviation) * 15
        else:
            features_df['risk_route'] = 0
        
        # Component 4: Speed Violations (10%)
        # Assume speed limit is 60 km/h for urban areas
        speed_limit = 60
        features_df['speed_violation'] = (features_df['max_speed_kmh'] - speed_limit).clip(lower=0)
        max_violation = features_df['speed_violation'].max()
        if max_violation > 0:
            features_df['risk_speed'] = (features_df['speed_violation'] / max_violation) * 10
        else:
            features_df['risk_speed'] = 0
        
        # Component 5: Government Accident Context (20% - NEW)
        if has_gov_features and use_gov_context:
            max_gov_risk = features_df['gov_compound_risk'].max()
            if max_gov_risk > 0:
                features_df['risk_gov_context'] = (
                    features_df['gov_compound_risk'] / max_gov_risk
                ) * 20
            else:
                features_df['risk_gov_context'] = 0
            
            print(f"   🏛️ Government context contributing up to 20 points to risk score")
        else:
            features_df['risk_gov_context'] = 0
            print(f"   ⚠️ Government context not available - using 0 points")
        
        # Total Risk Score (0-100)
        features_df['risk_score'] = (
            features_df['risk_if'] + 
            features_df['risk_dbscan'] + 
            features_df['risk_route'] + 
            features_df['risk_speed'] +
            features_df['risk_gov_context']  # NEW
        ).clip(upper=100)
        
        # Risk Categories
        features_df['risk_level'] = pd.cut(
            features_df['risk_score'],
            bins=[0, 30, 60, 100],
            labels=['Low', 'Medium', 'High']
        )
        
        print(f"   ✅ Risk scores calculated")
        print(f"\n   📊 Risk Distribution:")
        print(f"      Low Risk (0-30): {(features_df['risk_level']=='Low').sum()}")
        print(f"      Medium Risk (31-60): {(features_df['risk_level']=='Medium').sum()}")
        print(f"      High Risk (61-100): {(features_df['risk_level']=='High').sum()}")
        
        return features_df
    
    def aggregate_driver_scores(self, features_df):
        """Aggregate trip-level scores to driver-level"""
        print("\n👤 Aggregating driver-level metrics...")
        
        driver_metrics = features_df.groupby('driver_id').agg({
            'risk_score': ['mean', 'max', 'std'],
            'anomaly_if': 'sum',
            'is_outlier_dbscan': 'sum',
            'route_deviation_score': 'mean',
            'avg_speed_kmh': 'mean',
            'max_speed_kmh': 'max',
            'trip_id': 'count'
        }).reset_index()
        
        # Flatten column names
        driver_metrics.columns = [
            'driver_id', 'risk_score_mean', 'risk_score_max', 'risk_score_std',
            'anomalous_trips', 'outlier_trips', 'avg_route_deviation',
            'avg_speed', 'max_speed_ever', 'total_trips'
        ]
        
        # Calculate anomaly rate
        driver_metrics['anomaly_rate'] = (
            driver_metrics['anomalous_trips'] / driver_metrics['total_trips'] * 100
        )
        
        # Final driver risk score (weighted average)
        driver_metrics['driver_risk_score'] = (
            driver_metrics['risk_score_mean'] * 0.6 +
            driver_metrics['risk_score_max'] * 0.3 +
            driver_metrics['anomaly_rate'] * 0.1
        ).clip(upper=100)
        
        # Driver risk level
        driver_metrics['driver_risk_level'] = pd.cut(
            driver_metrics['driver_risk_score'],
            bins=[0, 30, 60, 100],
            labels=['Low', 'Medium', 'High']
        )
        
        print(f"   ✅ Processed {len(driver_metrics)} drivers")
        
        return driver_metrics
    
    def save_models(self, output_dir='models/trained'):
        """Save trained models"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        with open(f'{output_dir}/scaler.pkl', 'wb') as f:
            pickle.dump(self.scaler, f)
        
        with open(f'{output_dir}/isolation_forest.pkl', 'wb') as f:
            pickle.dump(self.isolation_forest, f)
        
        with open(f'{output_dir}/dbscan.pkl', 'wb') as f:
            pickle.dump(self.dbscan, f)
        
        print(f"\n💾 Models saved to {output_dir}/")
    
    def load_models(self, model_dir='models/trained'):
        """Load pre-trained models"""
        with open(f'{model_dir}/scaler.pkl', 'rb') as f:
            self.scaler = pickle.load(f)
        
        with open(f'{model_dir}/isolation_forest.pkl', 'rb') as f:
            self.isolation_forest = pickle.load(f)
        
        with open(f'{model_dir}/dbscan.pkl', 'rb') as f:
            self.dbscan = pickle.load(f)
        
        print(f"✅ Models loaded from {model_dir}/")
    
    def run_full_pipeline(self, trips_path, drivers_path, save_results=True, use_government_data=True):
        """Execute complete ML pipeline with optional government data integration"""
        
        print("\n" + "="*70)
        print(" "*20 + "GIG-SAFE ML PIPELINE")
        print("="*70)
        
        # Step 1: Load data
        trips_df, drivers_df = self.load_data(trips_path, drivers_path)
        
        # Step 1.5: Load government accident data (NEW)
        government_df = None
        if use_government_data:
            try:
                print("\n🏛️ Loading government accident data...")
                from app.services.government_data import GovernmentDataService
                
                gov_service = GovernmentDataService()
                government_df = gov_service.fetch_accident_data()
                
                if not government_df.empty:
                    print(f"   ✅ Loaded government data for {len(government_df)} states/UTs")
                else:
                    print(f"   ⚠️ Government data empty - continuing without context")
                    
            except Exception as e:
                print(f"   ⚠️ Could not load government data: {e}")
                print(f"   ⚠️ Continuing without government context")
        
        # Step 2: Feature extraction (now with government context)
        features_df = self.extract_features(trips_df, government_df)
        
        # Step 3: Anomaly detection
        features_df = self.detect_anomalies_isolation_forest(features_df)
        
        # Step 4: Clustering
        features_df = self.cluster_behavior_patterns(features_df)
        
        # Step 5: Risk scoring (now includes government context)
        features_df = self.calculate_risk_scores(features_df, use_gov_context=(government_df is not None))
        
        # Step 6: Driver aggregation
        driver_metrics = self.aggregate_driver_scores(features_df)
        
        # Step 7: Save results
        if save_results:
            import os
            os.makedirs('data/processed', exist_ok=True)
            features_df.to_csv('data/processed/trip_analysis.csv', index=False)
            driver_metrics.to_csv('data/processed/driver_risk_scores.csv', index=False)
            print("\n💾 Results saved:")
            print("   📁 data/processed/trip_analysis.csv")
            print("   📁 data/processed/driver_risk_scores.csv")
        
        # Step 8: Save models
        self.save_models()
        
        print("\n" + "="*70)
        print("✅ ML PIPELINE COMPLETE!")
        print("="*70)
        
        return features_df, driver_metrics


# For direct execution
if __name__ == "__main__":
    import os
    os.makedirs('data/processed', exist_ok=True)
    
    pipeline = GigSafeMLPipeline()
    
    features_df, driver_metrics = pipeline.run_full_pipeline(
        trips_path='data/synthetic/trips.csv',
        drivers_path='data/synthetic/drivers.csv',
        save_results=True
    )
    
    print("\n📊 FINAL SUMMARY:")
    print(f"   Total trips analyzed: {len(features_df)}")
    print(f"   Anomalous trips: {features_df['anomaly_if'].sum()}")
    print(f"   High-risk drivers: {(driver_metrics['driver_risk_level']=='High').sum()}")
    print(f"   Average driver risk score: {driver_metrics['driver_risk_score'].mean():.2f}")
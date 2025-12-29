# backend/app/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import pickle
from datetime import datetime
import uvicorn

# Initialize FastAPI app
app = FastAPI(
    title="GIG-SAFE API",
    description="Intelligent Gig Worker Verification & Safety System",
    version="1.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# DATA LOADING (Run once at startup)
# ============================================================================

print("🚀 Starting GIG-SAFE API...")
print("📂 Loading data and models...")

# Load datasets
try:
    drivers_df = pd.read_csv('data/synthetic/drivers.csv')
    trips_df = pd.read_csv('data/processed/trip_analysis.csv')
    driver_risk_df = pd.read_csv('data/processed/driver_risk_scores.csv')
    
    print(f"✅ Loaded {len(drivers_df)} drivers")
    print(f"✅ Loaded {len(trips_df)} trips")
    print(f"✅ Loaded {len(driver_risk_df)} driver risk scores")
    
except Exception as e:
    print(f"❌ Error loading data: {e}")
    print("⚠️  Make sure you've run the data generation and training scripts!")
    drivers_df = pd.DataFrame()
    trips_df = pd.DataFrame()
    driver_risk_df = pd.DataFrame()

# Load ML models
try:
    with open('models/trained/isolation_forest.pkl', 'rb') as f:
        isolation_forest_model = pickle.load(f)
    
    with open('models/trained/dbscan.pkl', 'rb') as f:
        dbscan_model = pickle.load(f)
    
    with open('models/trained/scaler.pkl', 'rb') as f:
        scaler_model = pickle.load(f)
    
    print("✅ Loaded ML models")
    
except Exception as e:
    print(f"⚠️  Could not load ML models: {e}")
    isolation_forest_model = None
    dbscan_model = None
    scaler_model = None

print("✅ GIG-SAFE API Ready!")
print("=" * 60)

# ============================================================================
# PYDANTIC MODELS (Data Validation)
# ============================================================================

class DriverIdentity(BaseModel):
    """Driver identity information"""
    name: str
    driver_id: str
    aadhaar: str
    phone: str
    vehicle_number: str
    vehicle_type: str

class EmploymentInfo(BaseModel):
    """Employment details"""
    company: str
    status: str
    join_date: str

class SafetyInfo(BaseModel):
    """Safety and risk information"""
    risk_score: float
    risk_level: str
    total_trips: int
    anomalous_trips: int
    anomaly_rate: float
    last_incident: Optional[str]

class LocationInfo(BaseModel):
    """Last known location"""
    last_known_lat: float
    last_known_lon: float
    timestamp: str
    trip_status: str

class DriverVerification(BaseModel):
    """Complete driver verification response"""
    identity: DriverIdentity
    employment: EmploymentInfo
    safety: SafetyInfo
    location: LocationInfo

class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_drivers_monitored: int
    active_trips: int
    high_risk_drivers: int
    anomalies_detected_today: int
    average_risk_score: float
    system_health: str

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_driver_by_id(driver_id: str):
    """Get driver information by ID"""
    driver = drivers_df[drivers_df['driver_id'] == driver_id]
    
    if driver.empty:
        return None
    
    return driver.iloc[0]

def get_driver_risk(driver_id: str):
    """Get driver risk information"""
    risk = driver_risk_df[driver_risk_df['driver_id'] == driver_id]
    
    if risk.empty:
        return None
    
    return risk.iloc[0]

def get_last_trip(driver_id: str):
    """Get driver's last trip"""
    driver_trips = trips_df[trips_df['driver_id'] == driver_id]
    
    if driver_trips.empty:
        return None
    
    # Sort by start_time and get the last trip
    driver_trips = driver_trips.sort_values('start_time', ascending=False)
    return driver_trips.iloc[0]

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
def root():
    """API root endpoint - System status"""
    return {
        "system": "GIG-SAFE",
        "version": "1.0.0",
        "status": "operational",
        "description": "Intelligent Gig Worker Verification & Safety System",
        "endpoints": {
            "verification": "/api/verify/{driver_id}",
            "dashboard": "/api/dashboard/stats",
            "high_risk": "/api/drivers/high-risk",
            "alerts": "/api/alerts/recent",
            "docs": "/docs"
        },
        "total_drivers": len(drivers_df),
        "total_trips": len(trips_df),
        "models_loaded": isolation_forest_model is not None
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "data_loaded": not drivers_df.empty,
        "models_loaded": isolation_forest_model is not None
    }

@app.get("/api/verify/{driver_id}", response_model=DriverVerification)
def verify_driver(driver_id: str):
    """
    🚨 LAW ENFORCEMENT VERIFICATION ENDPOINT
    
    Instant driver verification for authorities during incidents.
    
    Use Case: Police officer stops a delivery driver and needs immediate verification.
    
    Args:
        driver_id: Driver ID (format: DRV00001 to DRV00100)
    
    Returns:
        Complete driver profile with identity, employment, safety, and location info
    """
    
    # Get driver information
    driver = get_driver_by_id(driver_id)
    
    if driver is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Driver {driver_id} not found in database"
        )
    
    # Get risk information
    risk_info = get_driver_risk(driver_id)
    
    if risk_info is None:
        raise HTTPException(
            status_code=404,
            detail=f"Risk information not available for driver {driver_id}"
        )
    
    # Get last trip for location
    last_trip = get_last_trip(driver_id)
    
    if last_trip is None:
        # No trips yet - use default location
        last_lat, last_lon = 26.9124, 75.7873  # Jaipur center
        last_timestamp = datetime.now().isoformat()
        trip_status = "No trips yet"
    else:
        last_lat = float(last_trip['dropoff_lat'])
        last_lon = float(last_trip['dropoff_lon'])
        last_timestamp = str(last_trip['end_time'])
        trip_status = "Completed"
    
    # Determine risk level
    risk_score = float(risk_info['driver_risk_score'])
    if risk_score < 30:
        risk_level = "Low"
    elif risk_score < 60:
        risk_level = "Medium"
    else:
        risk_level = "High"
    
    # Build response
    verification_response = DriverVerification(
        identity=DriverIdentity(
            name=str(driver['name']),
            driver_id=str(driver['driver_id']),
            aadhaar=str(driver['aadhaar']),
            phone=str(driver['phone']),
            vehicle_number=str(driver['vehicle_number']),
            vehicle_type=str(driver['vehicle_type'])
        ),
        employment=EmploymentInfo(
            company=str(driver['company']),
            status="Active",  # In real system, check actual status
            join_date=str(driver['join_date'])
        ),
        safety=SafetyInfo(
            risk_score=risk_score,
            risk_level=risk_level,
            total_trips=int(risk_info['total_trips']),
            anomalous_trips=int(risk_info['anomalous_trips']),
            anomaly_rate=float(risk_info['anomaly_rate']),
            last_incident=last_timestamp if risk_info['anomalous_trips'] > 0 else None
        ),
        location=LocationInfo(
            last_known_lat=last_lat,
            last_known_lon=last_lon,
            timestamp=last_timestamp,
            trip_status=trip_status
        )
    )
    
    return verification_response


@app.get("/api/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats():
    """
    📊 REAL-TIME MONITORING DASHBOARD STATISTICS
    
    Provides overview of system status and current monitoring metrics.
    
    Use Case: Admin dashboard showing system-wide statistics
    
    Returns:
        Dashboard statistics including driver counts, risk levels, and anomalies
    """
    
    if drivers_df.empty or driver_risk_df.empty or trips_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded. Please run data generation and training scripts."
        )
    
    # Total drivers
    total_drivers = len(drivers_df)
    
    # Simulate active trips (in real system, query current trips)
    # For demo: assume 40-50% of drivers are currently active
    import random
    random.seed(42)
    active_trips = random.randint(int(total_drivers * 0.4), int(total_drivers * 0.5))
    
    # High risk drivers (risk score > 60)
    high_risk_count = len(driver_risk_df[driver_risk_df['driver_risk_score'] > 60])
    
    # Anomalies detected today (simulate - in real system, filter by today's date)
    # For demo: count recent anomalies
    total_anomalies = int(trips_df['anomaly_if'].sum())
    
    # Average risk score across all drivers
    avg_risk = float(driver_risk_df['driver_risk_score'].mean())
    
    # System health check
    system_health = "Operational"
    if isolation_forest_model is None:
        system_health = "Degraded - Models not loaded"
    
    stats = DashboardStats(
        total_drivers_monitored=total_drivers,
        active_trips=active_trips,
        high_risk_drivers=high_risk_count,
        anomalies_detected_today=total_anomalies,
        average_risk_score=round(avg_risk, 2),
        system_health=system_health
    )
    
    return stats


@app.get("/api/drivers/high-risk")
def get_high_risk_drivers(limit: int = 20):
    """
    ⚠️ HIGH-RISK DRIVERS LIST
    
    Returns list of drivers with highest risk scores requiring attention.
    
    Use Case: Supervisors reviewing drivers that need intervention
    
    Args:
        limit: Maximum number of drivers to return (default: 20)
    
    Returns:
        List of high-risk drivers with their metrics
    """
    
    if driver_risk_df.empty or drivers_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )
    
    # Get drivers sorted by risk score (highest first)
    high_risk = driver_risk_df.nlargest(limit, 'driver_risk_score')
    
    result = []
    for _, risk_data in high_risk.iterrows():
        driver_id = risk_data['driver_id']
        driver_info = get_driver_by_id(driver_id)
        
        if driver_info is not None:
            risk_score = float(risk_data['driver_risk_score'])
            
            # Determine risk level
            if risk_score >= 60:
                risk_level = "High"
            elif risk_score >= 30:
                risk_level = "Medium"
            else:
                risk_level = "Low"
            
            result.append({
                "driver_id": driver_id,
                "name": str(driver_info['name']),
                "company": str(driver_info['company']),
                "vehicle_number": str(driver_info['vehicle_number']),
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level,
                "total_trips": int(risk_data['total_trips']),
                "anomalous_trips": int(risk_data['anomalous_trips']),
                "anomaly_rate": round(float(risk_data['anomaly_rate']), 2),
                "requires_action": risk_score > 50
            })
    
    return {
        "count": len(result),
        "drivers": result
    }


@app.get("/api/alerts/recent")
def get_recent_alerts(limit: int = 20):
    """
    🚨 RECENT ANOMALY ALERTS
    
    Returns recent trips flagged as anomalous by the ML system.
    
    Use Case: Real-time monitoring of suspicious activity
    
    Args:
        limit: Maximum number of alerts to return (default: 20)
    
    Returns:
        List of recent anomalous trips with details
    """
    
    if trips_df.empty or drivers_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )
    
    # Get anomalous trips
    anomalous_trips = trips_df[trips_df['anomaly_if'] == 1].copy()
    
    if anomalous_trips.empty:
        return {
            "count": 0,
            "alerts": []
        }
    
    # Sort by start_time (most recent first) and limit
    anomalous_trips = anomalous_trips.sort_values('start_time', ascending=False).head(limit)
    
    alerts = []
    for _, trip in anomalous_trips.iterrows():
        driver_info = get_driver_by_id(trip['driver_id'])
        
        if driver_info is not None:
            # Determine alert type based on trip characteristics
            alert_type = "Behavioral Anomaly"
            if trip['max_speed_kmh'] > 80:
                alert_type = "Rash Driving"
            elif trip['route_deviation_score'] > 20:
                alert_type = "Route Deviation"
            elif trip['is_outlier_dbscan'] == 1:
                alert_type = "Unusual Pattern"
            
            # Determine severity
            risk_score = float(trip['risk_score'])
            if risk_score >= 70:
                severity = "High"
            elif risk_score >= 40:
                severity = "Medium"
            else:
                severity = "Low"
            
            alerts.append({
                "alert_id": str(trip['trip_id']),
                "timestamp": str(trip['start_time']),
                "driver_id": str(trip['driver_id']),
                "driver_name": str(driver_info['name']),
                "company": str(driver_info['company']),
                "alert_type": alert_type,
                "severity": severity,
                "risk_score": round(risk_score, 2),
                "location": {
                    "lat": float(trip['pickup_lat']),
                    "lon": float(trip['pickup_lon'])
                },
                "details": {
                    "max_speed": round(float(trip['max_speed_kmh']), 2),
                    "avg_speed": round(float(trip['avg_speed_kmh']), 2),
                    "distance_km": round(float(trip['distance_km']), 2),
                    "duration_min": round(float(trip['duration_minutes']), 2),
                    "route_deviation": round(float(trip['route_deviation_score']), 2)
                }
            })
    
    return {
        "count": len(alerts),
        "alerts": alerts
    }


# ============================================================================
# RUN THE APP
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 Starting GIG-SAFE API Server")
    print("=" * 60)
    print("\n📍 API will be available at:")
    print("   http://localhost:8000")
    print("\n📖 Interactive API docs at:")
    print("   http://localhost:8000/docs")
    print("\n" + "=" * 60 + "\n")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
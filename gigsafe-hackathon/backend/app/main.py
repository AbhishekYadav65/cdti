# backend/app/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import pickle
from datetime import datetime
import uvicorn
import sys
import random
import logging

sys.path.append('.')
from app.services.government_data import GovernmentDataService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

logger.info("🚀 Starting GIG-SAFE API...")
logger.info("📂 Loading data and models...")

# Load datasets
try:
    drivers_df = pd.read_csv('data/synthetic/drivers.csv')
    trips_df = pd.read_csv('data/processed/trip_analysis.csv')
    driver_risk_df = pd.read_csv('data/processed/driver_risk_scores.csv')
    
    logger.info(f"✅ Loaded {len(drivers_df)} drivers")
    logger.info(f"✅ Loaded {len(trips_df)} trips")
    logger.info(f"✅ Loaded {len(driver_risk_df)} driver risk scores")
    
except Exception as e:
    logger.error(f"❌ Error loading data: {e}")
    logger.warning("⚠️  Make sure you've run the data generation and training scripts!")
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
    
    logger.info("✅ Loaded ML models")
    
except Exception as e:
    logger.warning(f"⚠️  Could not load ML models: {e}")
    isolation_forest_model = None
    dbscan_model = None
    scaler_model = None

logger.info("✅ GIG-SAFE API Ready!")
logger.info("=" * 60)

# ============================================================================
# PYDANTIC MODELS (Data Validation)
# ============================================================================

class DriverIdentity(BaseModel):
    """Driver identity information"""
    name: str
    driver_id: str
    worker_type: str
    aadhaar: str
    phone: str
    vehicle_number: str
    vehicle_type: str

class EmploymentInfo(BaseModel):
    """Employment details"""
    company: str
    status: str
    join_date: str
    # Banking-specific fields (optional)
    bank_name: Optional[str] = None
    agent_id: Optional[str] = None
    authorization_expiry: Optional[str] = None
    aeps_enabled: Optional[bool] = None

class SafetyInfo(BaseModel):
    """Safety and risk information"""
    risk_score: float
    risk_level: str
    total_trips: int
    anomalous_trips: int
    anomaly_rate: float
    last_incident: Optional[str]
    government_context: Optional[dict] = None

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
        "models_loaded": isolation_forest_model is not None,
        "government_data_integrated": True
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
# VERIFICATION ENDPOINT (LAW ENFORCEMENT)
# ============================================================================

@app.get("/api/verify/{driver_id}", response_model=DriverVerification)
def verify_driver(driver_id: str):
    """
    🚨 LAW ENFORCEMENT VERIFICATION ENDPOINT
    
    Instant driver verification for authorities during incidents.
    Now includes real Government of India accident data calibration.
    
    Use Case: Police officer stops a delivery driver and needs immediate verification.
    
    Args:
        driver_id: Driver ID (format: DRV00001 to DRV00100)
    
    Returns:
        Complete driver profile with identity, employment, safety, location, and government context
    """
    
    logger.info(f"Verification request for driver: {driver_id}")
    
    # Get driver information
    driver = get_driver_by_id(driver_id)
    
    if driver is None:
        logger.warning(f"Driver not found: {driver_id}")
        raise HTTPException(
            status_code=404, 
            detail=f"Driver {driver_id} not found in database"
        )
    
    # Get risk information
    risk_info = get_driver_risk(driver_id)
    
    if risk_info is None:
        logger.error(f"Risk information not available for: {driver_id}")
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
        logger.info(f"No trips found for {driver_id}, using default location")
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
    
    # Get government accident context
    government_context = None
    try:
        gov_service = GovernmentDataService()
        
        # Get Rajasthan data (where drivers operate)
        state_info = gov_service.get_state_risk("Rajasthan")
        
        if state_info:
            # Calculate how much government data contributes to risk
            # Check if last trip has gov context features
            if last_trip is not None and 'risk_gov_context' in last_trip.index:
                gov_contribution = float(last_trip['risk_gov_context'])
            else:
                # Estimate based on formula (20% max)
                gov_contribution = (state_info['risk_index'] / 100) * 20
            
            government_context = {
                "state": state_info['state'],
                "state_risk_index": state_info['risk_index'],
                "total_accidents_2022": state_info['total_accidents_2022'],
                "contributes_to_score": round(gov_contribution, 2),
                "data_source": "Government of India - Ministry of Road Transport",
                "explanation": f"Driver operates in {state_info['state']} (accident risk index: {state_info['risk_index']}/100). Government data adds ~{round(gov_contribution, 1)} points to risk score."
            }
            logger.info(f"Government context loaded for {driver_id}")
    except Exception as e:
        logger.warning(f"Could not load government context for {driver_id}: {e}")
        government_context = None
    
    # Build response
    verification_response = DriverVerification(
        identity=DriverIdentity(
            name=str(driver['name']),
            driver_id=str(driver['driver_id']),
            worker_type=str(driver.get('worker_type', 'Delivery')),
            aadhaar=str(driver['aadhaar']),
            phone=str(driver['phone']),
            vehicle_number=str(driver['vehicle_number']) if pd.notna(driver.get('vehicle_number')) else 'N/A',
            vehicle_type=str(driver['vehicle_type']) if pd.notna(driver.get('vehicle_type')) else 'Unknown'
        ),
        employment=EmploymentInfo(
            company=str(driver['company']),
            status="Active",  # In real system, check actual status
            join_date=str(driver['join_date']),
            # Banking-specific fields
            bank_name=str(driver['bank_name']) if pd.notna(driver.get('bank_name')) else None,
            agent_id=str(driver['agent_id']) if pd.notna(driver.get('agent_id')) else None,
            authorization_expiry=str(driver['authorization_expiry']) if pd.notna(driver.get('authorization_expiry')) else None,
            aeps_enabled=bool(driver['aeps_enabled']) if pd.notna(driver.get('aeps_enabled')) else None
        ),
        safety=SafetyInfo(
            risk_score=risk_score,
            risk_level=risk_level,
            total_trips=int(risk_info['total_trips']),
            anomalous_trips=int(risk_info['anomalous_trips']),
            anomaly_rate=float(risk_info['anomaly_rate']),
            last_incident=last_timestamp if risk_info['anomalous_trips'] > 0 else None,
            government_context=government_context
        ),
        location=LocationInfo(
            last_known_lat=last_lat,
            last_known_lon=last_lon,
            timestamp=last_timestamp,
            trip_status=trip_status
        )
    )
    
    logger.info(f"Verification successful for {driver_id} - Risk Level: {risk_level}")
    return verification_response

# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

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
        logger.error("Dashboard stats requested but data not loaded")
        raise HTTPException(
            status_code=503,
            detail="Data not loaded. Please run data generation and training scripts."
        )
    
    # Total drivers
    total_drivers = len(drivers_df)
    
    # Simulate active trips (in real system, query current trips)
    # For demo: assume 40-50% of drivers are currently active
    random.seed(42)  # For consistent demo results
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
    
    logger.info(f"Dashboard stats generated - High Risk: {high_risk_count}, Anomalies: {total_anomalies}")
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
        logger.error("High-risk drivers requested but data not loaded")
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
            
            # Determine risk level (standardized thresholds)
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
                "vehicle_number": str(driver_info['vehicle_number']) if pd.notna(driver_info.get('vehicle_number')) else 'N/A',
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level,
                "total_trips": int(risk_data['total_trips']),
                "anomalous_trips": int(risk_data['anomalous_trips']),
                "anomaly_rate": round(float(risk_data['anomaly_rate']), 2),
                "requires_action": risk_score > 60  # Standardized to match risk_level
            })
    
    logger.info(f"Returned {len(result)} high-risk drivers")
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
        logger.error("Recent alerts requested but data not loaded")
        raise HTTPException(
            status_code=503,
            detail="Data not loaded"
        )
    
    # Get anomalous trips
    anomalous_trips = trips_df[trips_df['anomaly_if'] == 1].copy()
    
    if anomalous_trips.empty:
        logger.info("No anomalous trips found")
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
    
    logger.info(f"Returned {len(alerts)} recent alerts")
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
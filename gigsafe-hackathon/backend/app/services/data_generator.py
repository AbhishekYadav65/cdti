# backend/app/services/data_generator.py

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
import json

# Set seeds for reproducibility
np.random.seed(42)
random.seed(42)
fake = Faker('en_IN')
Faker.seed(42)


class GigWorkerDataGenerator:
    """Generate synthetic data for gig workers, trips, and GPS traces"""
    
    def __init__(self, num_drivers=100, days=30):
        self.num_drivers = num_drivers
        self.days = days
        self.base_lat = 26.9124  # Jaipur latitude
        self.base_lon = 75.7873  # Jaipur longitude
        
    def generate_driver_profiles(self):
        """Generate realistic driver profiles with risk categories"""
        drivers = []
        
        companies = ['Zomato', 'Swiggy', 'Uber', 'Ola', 'Dunzo', 'Rapido']
        
        for i in range(self.num_drivers):
            # Assign risk categories: 70% low, 25% medium, 5% high
            risk_category = random.choices(
                ['low', 'medium', 'high'], 
                weights=[70, 25, 5]
            )[0]
            
            driver = {
                'driver_id': f'DRV{str(i+1).zfill(5)}',
                'name': fake.name(),
                'phone': fake.phone_number(),
                'aadhaar': fake.aadhaar_id(),
                'pan': fake.bothify(text='?????####?').upper(),
                'vehicle_number': f'RJ{random.randint(10,20)} {fake.bothify(text="??####").upper()}',
                'vehicle_type': random.choice(['Bike', 'Scooter', 'Car']),
                'company': random.choice(companies),
                'join_date': fake.date_between(start_date='-2y', end_date='-1m'),
                'age': random.randint(21, 45),
                'experience_years': random.randint(1, 8),
                'risk_category': risk_category,
                'base_skill_level': random.uniform(0.6, 0.95)  # Hidden attribute affecting performance
            }
            drivers.append(driver)
        
        return pd.DataFrame(drivers)
    
    def generate_trip(self, driver_id, driver_data, trip_date):
        """Generate a single trip with realistic characteristics"""
        
        risk_category = driver_data['risk_category']
        skill_level = driver_data['base_skill_level']
        
        # Determine if this trip will be anomalous based on driver risk
        anomaly_probability = {
            'low': 0.05,
            'medium': 0.15,
            'high': 0.35
        }
        is_anomalous = random.random() < anomaly_probability[risk_category]
        
        # Trip timing
        hour = random.randint(8, 23)
        minute = random.randint(0, 59)
        start_time = datetime.combine(trip_date, datetime.min.time()) + \
                     timedelta(hours=hour, minutes=minute)
        
        # Trip characteristics
        if not is_anomalous:
            # Normal trip
            distance = random.uniform(2, 15)  # km
            base_time = distance * random.uniform(3, 5)  # minutes (normal speed)
            speed_factor = skill_level * random.uniform(0.9, 1.1)
            duration = base_time / speed_factor
            avg_speed = (distance / duration) * 60  # km/h
            max_speed = avg_speed * random.uniform(1.1, 1.3)
            
            # Route deviation (small for normal trips)
            route_deviation_score = random.uniform(0, 10)
            
        else:
            # Anomalous trip - choose type of anomaly
            anomaly_type = random.choice(['rash_driving', 'route_deviation', 'delayed'])
            
            distance = random.uniform(3, 20)
            
            if anomaly_type == 'rash_driving':
                # Too fast driving
                base_time = distance * random.uniform(1.5, 2.5)
                duration = base_time * random.uniform(0.7, 0.9)
                avg_speed = (distance / duration) * 60
                max_speed = avg_speed * random.uniform(1.5, 2.2)  # Excessive speed
                route_deviation_score = random.uniform(5, 15)
                
            elif anomaly_type == 'route_deviation':
                # Unusual route
                base_time = distance * random.uniform(3, 5)
                duration = base_time * random.uniform(1.2, 1.5)  # Takes longer
                avg_speed = (distance / duration) * 60
                max_speed = avg_speed * random.uniform(1.1, 1.4)
                route_deviation_score = random.uniform(20, 50)  # High deviation
                
            else:  # delayed
                # Unexplained delays
                base_time = distance * random.uniform(3, 5)
                duration = base_time * random.uniform(1.5, 2.5)  # Much slower
                avg_speed = (distance / duration) * 60
                max_speed = avg_speed * random.uniform(1.1, 1.3)
                route_deviation_score = random.uniform(0, 10)
        
        # Generate pickup and dropoff locations
        pickup_lat = self.base_lat + random.uniform(-0.1, 0.1)
        pickup_lon = self.base_lon + random.uniform(-0.1, 0.1)
        
        # Dropoff is roughly in the direction of distance
        angle = random.uniform(0, 2 * np.pi)
        distance_degree = distance / 111  # Rough conversion: 1 degree ≈ 111 km
        dropoff_lat = pickup_lat + distance_degree * np.cos(angle)
        dropoff_lon = pickup_lon + distance_degree * np.sin(angle)
        
        # Generate GPS trace
        gps_trace = self._generate_gps_trace(
            pickup_lat, pickup_lon, 
            dropoff_lat, dropoff_lon,
            start_time, duration, 
            max_speed, is_anomalous
        )
        
        trip = {
            'trip_id': f'TRP{fake.uuid4()[:12].upper()}',
            'driver_id': driver_id,
            'start_time': start_time,
            'end_time': start_time + timedelta(minutes=duration),
            'distance_km': round(distance, 2),
            'duration_minutes': round(duration, 2),
            'avg_speed_kmh': round(avg_speed, 2),
            'max_speed_kmh': round(max_speed, 2),
            'pickup_lat': round(pickup_lat, 6),
            'pickup_lon': round(pickup_lon, 6),
            'dropoff_lat': round(dropoff_lat, 6),
            'dropoff_lon': round(dropoff_lon, 6),
            'route_deviation_score': round(route_deviation_score, 2),
            'hour_of_day': hour,
            'day_of_week': trip_date.weekday(),
            'is_night': 1 if hour < 6 or hour > 22 else 0,
            'is_anomalous': int(is_anomalous),
            'gps_trace': json.dumps(gps_trace),  # Store as JSON string
            'weather': random.choice(['Clear', 'Cloudy', 'Rainy', 'Foggy']),
            'traffic_level': random.choice(['Low', 'Medium', 'High'])
        }
        
        return trip
    
    def _generate_gps_trace(self, start_lat, start_lon, end_lat, end_lon, 
                           start_time, duration, max_speed, is_anomalous):
        """Generate GPS trace points for a trip"""
        
        num_points = max(10, int(duration / 0.167))  # Point every ~10 seconds
        gps_trace = []
        
        for i in range(num_points):
            progress = i / (num_points - 1) if num_points > 1 else 1
            
            # Linear interpolation between start and end
            lat = start_lat + (end_lat - start_lat) * progress
            lon = start_lon + (end_lon - start_lon) * progress
            
            # Add some noise to make it realistic
            lat += random.gauss(0, 0.0002)
            lon += random.gauss(0, 0.0002)
            
            # Add extra deviation for anomalous trips
            if is_anomalous and random.random() > 0.7:
                lat += random.gauss(0, 0.001)
                lon += random.gauss(0, 0.001)
            
            # Calculate speed for this segment
            if i == 0:
                speed = 0
            else:
                speed = random.uniform(0, max_speed)
            
            point = {
                'lat': round(lat, 6),
                'lon': round(lon, 6),
                'timestamp': (start_time + timedelta(minutes=duration * progress)).isoformat(),
                'speed_kmh': round(speed, 2)
            }
            gps_trace.append(point)
        
        return gps_trace
    
    def generate_complete_dataset(self):
        """Generate complete dataset: drivers and trips"""
        
        print(f"🚀 Generating synthetic data...")
        print(f"   Drivers: {self.num_drivers}")
        print(f"   Days: {self.days}")
        
        # Generate drivers
        print("\n📊 Step 1/2: Generating driver profiles...")
        drivers_df = self.generate_driver_profiles()
        print(f"   ✅ Created {len(drivers_df)} driver profiles")
        print(f"   - Low risk: {(drivers_df['risk_category']=='low').sum()}")
        print(f"   - Medium risk: {(drivers_df['risk_category']=='medium').sum()}")
        print(f"   - High risk: {(drivers_df['risk_category']=='high').sum()}")
        
        # Generate trips
        print("\n🚗 Step 2/2: Generating trip history...")
        all_trips = []
        start_date = datetime.now() - timedelta(days=self.days)
        
        for idx, driver in drivers_df.iterrows():
            driver_id = driver['driver_id']
            
            # Generate 2-5 trips per day per driver
            for day in range(self.days):
                num_trips = random.randint(2, 5)
                trip_date = start_date + timedelta(days=day)
                
                for _ in range(num_trips):
                    trip = self.generate_trip(driver_id, driver, trip_date.date())
                    all_trips.append(trip)
            
            if (idx + 1) % 10 == 0:
                print(f"   Progress: {idx + 1}/{self.num_drivers} drivers")
        
        trips_df = pd.DataFrame(all_trips)
        
        print(f"\n   ✅ Created {len(trips_df)} trips")
        print(f"   - Normal trips: {(trips_df['is_anomalous']==0).sum()}")
        print(f"   - Anomalous trips: {(trips_df['is_anomalous']==1).sum()}")
        print(f"   - Anomaly rate: {trips_df['is_anomalous'].mean()*100:.1f}%")
        
        return drivers_df, trips_df
    
    def save_data(self, drivers_df, trips_df, output_dir='backend/data/synthetic'):
        """Save generated data to CSV files"""
        
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        drivers_path = f'{output_dir}/drivers.csv'
        trips_path = f'{output_dir}/trips.csv'
        
        drivers_df.to_csv(drivers_path, index=False)
        trips_df.to_csv(trips_path, index=False)
        
        print(f"\n💾 Data saved successfully!")
        print(f"   📁 Drivers: {drivers_path}")
        print(f"   📁 Trips: {trips_path}")
        
        # Print file sizes
        import os
        drivers_size = os.path.getsize(drivers_path) / 1024  # KB
        trips_size = os.path.getsize(trips_path) / (1024 * 1024)  # MB
        print(f"\n   Size: Drivers={drivers_size:.1f} KB, Trips={trips_size:.1f} MB")
        
        return drivers_path, trips_path


# Main execution
if __name__ == "__main__":
    print("="*60)
    print("GIG-SAFE: Synthetic Data Generator")
    print("="*60)
    
    # Initialize generator
    generator = GigWorkerDataGenerator(num_drivers=100, days=30)
    
    # Generate data
    drivers_df, trips_df = generator.generate_complete_dataset()
    
    # Save to files
    generator.save_data(drivers_df, trips_df)
    
    print("\n" + "="*60)
    print("✅ Data generation complete!")
    print("="*60)
    print("\nNext step: Train ML models on this data")
    print("Run: python backend/scripts/train_models.py")
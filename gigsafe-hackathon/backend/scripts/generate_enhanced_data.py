# backend/scripts/generate_enhanced_data.py
"""
Enhanced data generator supporting:
- Delivery personnel (Zomato, Swiggy, Uber, etc.)
- Banking agents (AePS, account opening, loan collection)
"""

import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
import json
import sys
sys.path.append('.')

from app.services.data_generator import GigWorkerDataGenerator

# Set seeds
np.random.seed(42)
random.seed(42)
fake = Faker('en_IN')
Faker.seed(42)


class EnhancedGigWorkerGenerator(GigWorkerDataGenerator):
    """Extended generator with banking agent support"""
    
    def generate_driver_profiles(self):
        """Generate profiles for both delivery workers and banking agents"""
        
        workers = []
        
        # Companies by worker type
        delivery_companies = ['Zomato', 'Swiggy', 'Uber', 'Ola', 'Dunzo', 'Rapido']
        banks = ['State Bank of India', 'HDFC Bank', 'ICICI Bank', 'Axis Bank', 
                 'Punjab National Bank', 'Bank of Baroda']
        
        # 70 delivery workers, 30 banking agents
        num_delivery = 70
        num_banking = 30
        
        for i in range(self.num_drivers):
            # Determine worker type
            if i < num_delivery:
                worker_type = 'Delivery'
                company = random.choice(delivery_companies)
                vehicle_type = random.choice(['Bike', 'Scooter', 'Car'])
                vehicle_number = f'RJ{random.randint(10,20)} {fake.bothify(text="??####").upper()}'
                
                # Banking-specific fields (null for delivery)
                bank_name = None
                agent_id = None
                authorization_expiry = None
                aeps_enabled = False
                authorization_documents = None
                
            else:
                worker_type = 'Banking Agent'
                bank_name = random.choice(banks)
                company = f'{bank_name} - BC Network'
                vehicle_type = random.choice(['Bike', 'Car', 'None'])
                vehicle_number = f'RJ{random.randint(10,20)} {fake.bothify(text="??####").upper()}' if vehicle_type != 'None' else 'N/A'
                
                # Banking-specific fields
                agent_id = f'BC{random.randint(100000, 999999)}'
                # Authorization valid for 1-3 years from join date
                authorization_days = random.randint(365, 1095)
                authorization_expiry = fake.date_between(start_date='+180d', end_date='+1095d')
                aeps_enabled = random.choice([True, True, True, False])  # 75% have AePS
                authorization_documents = ['Aadhaar', 'PAN', 'Bank Certificate', 'Police Verification']
            
            # Risk categories
            risk_category = random.choices(
                ['low', 'medium', 'high'], 
                weights=[70, 25, 5]
            )[0]
            
            worker = {
                'driver_id': f'DRV{str(i+1).zfill(5)}',
                'worker_type': worker_type,
                'name': fake.name(),
                'phone': fake.phone_number(),
                'aadhaar': fake.aadhaar_id(),
                'pan': fake.bothify(text='?????####?').upper(),
                'vehicle_number': vehicle_number,
                'vehicle_type': vehicle_type,
                'company': company,
                
                # Banking-specific fields
                'bank_name': bank_name,
                'agent_id': agent_id,
                'authorization_expiry': str(authorization_expiry) if authorization_expiry else None,
                'aeps_enabled': aeps_enabled,
                'authorization_documents': ','.join(authorization_documents) if authorization_documents else None,
                
                'join_date': fake.date_between(start_date='-2y', end_date='-1m'),
                'age': random.randint(21, 45),
                'experience_years': random.randint(1, 8),
                'risk_category': risk_category,
                'base_skill_level': random.uniform(0.6, 0.95)
            }
            workers.append(worker)
        
        return pd.DataFrame(workers)
    
    def generate_trip(self, driver_id, driver_data, trip_date):
        """Generate trip/visit based on worker type"""
        
        worker_type = driver_data['worker_type']
        
        if worker_type == 'Delivery':
            # Use parent class delivery trip generation
            return super().generate_trip(driver_id, driver_data, trip_date)
        
        else:
            # Banking agent visit
            return self._generate_banking_visit(driver_id, driver_data, trip_date)
    
    def _generate_banking_visit(self, agent_id, agent_data, visit_date):
        """Generate banking agent household visit"""
        
        risk_category = agent_data['risk_category']
        
        # Determine if visit is anomalous
        anomaly_probability = {
            'low': 0.05,
            'medium': 0.15,
            'high': 0.35
        }
        is_anomalous = random.random() < anomaly_probability[risk_category]
        
        # Visit timing (banking agents work 9 AM - 6 PM mostly)
        hour = random.randint(9, 18)
        minute = random.randint(0, 59)
        start_time = datetime.combine(visit_date, datetime.min.time()) + \
                     timedelta(hours=hour, minutes=minute)
        
        # Visit characteristics
        visit_types = ['Account Opening', 'AePS Transaction', 'Loan Collection', 
                      'KYC Update', 'Passbook Entry', 'Cash Deposit']
        visit_type = random.choice(visit_types)
        
        if not is_anomalous:
            # Normal visit
            distance = random.uniform(1, 10)  # km
            duration = random.uniform(15, 45)  # minutes (longer than delivery)
            avg_speed = (distance / duration) * 60 if duration > 0 else 20
            max_speed = avg_speed * random.uniform(1.1, 1.3)
            
            route_deviation_score = random.uniform(0, 8)
            visit_duration_minutes = random.uniform(10, 30)  # Time at household
            
            # Transaction details (if applicable)
            if visit_type == 'AePS Transaction':
                transaction_amount = random.randint(500, 10000)
                transaction_successful = True
            else:
                transaction_amount = 0
                transaction_successful = None
                
        else:
            # Anomalous visit - red flags
            anomaly_type = random.choice(['suspicious_location', 'unusual_amount', 
                                         'late_hours', 'long_duration'])
            
            distance = random.uniform(2, 15)
            
            if anomaly_type == 'suspicious_location':
                # Far from usual area
                route_deviation_score = random.uniform(20, 50)
                duration = random.uniform(30, 90)
                visit_duration_minutes = random.uniform(5, 20)
                
            elif anomaly_type == 'unusual_amount':
                # Large transaction
                route_deviation_score = random.uniform(5, 15)
                duration = random.uniform(20, 50)
                visit_duration_minutes = random.uniform(15, 40)
                transaction_amount = random.randint(25000, 100000)  # High amount
                
            elif anomaly_type == 'late_hours':
                # Working unusual hours
                hour = random.randint(19, 22)
                start_time = datetime.combine(visit_date, datetime.min.time()) + \
                           timedelta(hours=hour, minutes=minute)
                route_deviation_score = random.uniform(5, 15)
                duration = random.uniform(20, 60)
                visit_duration_minutes = random.uniform(10, 30)
                
            else:  # long_duration
                # Unusually long visit
                route_deviation_score = random.uniform(5, 15)
                duration = random.uniform(30, 90)
                visit_duration_minutes = random.uniform(60, 180)  # Very long
            
            avg_speed = (distance / duration) * 60 if duration > 0 else 20
            max_speed = avg_speed * random.uniform(1.1, 1.4)
            
            if visit_type == 'AePS Transaction':
                transaction_amount = random.randint(500, 50000)
                # 20% chance of failed transaction in anomalous cases
                transaction_successful = random.choice([True, True, True, True, False])
            else:
                transaction_amount = 0
                transaction_successful = None
        
        # Generate locations
        pickup_lat = self.base_lat + random.uniform(-0.1, 0.1)
        pickup_lon = self.base_lon + random.uniform(-0.1, 0.1)
        
        angle = random.uniform(0, 2 * np.pi)
        distance_degree = distance / 111
        dropoff_lat = pickup_lat + distance_degree * np.cos(angle)
        dropoff_lon = pickup_lon + distance_degree * np.sin(angle)
        
        # Generate GPS trace (same as delivery)
        gps_trace = self._generate_gps_trace(
            pickup_lat, pickup_lon,
            dropoff_lat, dropoff_lon,
            start_time, duration,
            max_speed, is_anomalous
        )
        
        visit = {
            'trip_id': f'TRP{fake.uuid4()[:12].upper()}',
            'driver_id': agent_id,
            'worker_type': 'Banking Agent',
            'visit_type': visit_type,
            'start_time': start_time,
            'end_time': start_time + timedelta(minutes=duration),
            'distance_km': round(distance, 2),
            'duration_minutes': round(duration, 2),
            'visit_duration_minutes': round(visit_duration_minutes, 2),
            'avg_speed_kmh': round(avg_speed, 2),
            'max_speed_kmh': round(max_speed, 2),
            'pickup_lat': round(pickup_lat, 6),
            'pickup_lon': round(pickup_lon, 6),
            'dropoff_lat': round(dropoff_lat, 6),
            'dropoff_lon': round(dropoff_lon, 6),
            'route_deviation_score': round(route_deviation_score, 2),
            'hour_of_day': hour,
            'day_of_week': visit_date.weekday(),
            'is_night': 1 if hour < 6 or hour > 22 else 0,
            'is_anomalous': int(is_anomalous),
            'gps_trace': json.dumps(gps_trace),
            'weather': random.choice(['Clear', 'Cloudy', 'Rainy', 'Foggy']),
            'traffic_level': random.choice(['Low', 'Medium', 'High']),
            
            # Banking-specific
            'transaction_amount': transaction_amount,
            'transaction_successful': transaction_successful,
            'customer_verified': random.choice([True, False]) if not is_anomalous else False
        }
        
        return visit


def main():
    print("="*70)
    print("GIG-SAFE: ENHANCED DATA GENERATOR")
    print("Delivery Workers + Banking Agents")
    print("="*70)
    
    # Generate enhanced dataset
    generator = EnhancedGigWorkerGenerator(num_drivers=100, days=30)
    
    drivers_df, trips_df = generator.generate_complete_dataset()
    
    # Save (use correct path without 'backend' prefix)
    generator.save_data(drivers_df, trips_df, output_dir='data/synthetic')
    
    # Show breakdown
    print("\n" + "="*70)
    print("WORKER TYPE BREAKDOWN")
    print("="*70)
    print("\n📊 By Type:")
    print(drivers_df['worker_type'].value_counts())
    
    print("\n🚗 Delivery Companies:")
    delivery = drivers_df[drivers_df['worker_type'] == 'Delivery']
    print(delivery['company'].value_counts())
    
    print("\n🏦 Banking Agents:")
    banking = drivers_df[drivers_df['worker_type'] == 'Banking Agent']
    print(banking['bank_name'].value_counts())
    
    print(f"\n✅ AePS Enabled Agents: {banking['aeps_enabled'].sum()}/{len(banking)}")
    
    print("\n📋 Trip/Visit Breakdown:")
    print(trips_df['worker_type'].value_counts())
    
    print("\n" + "="*70)
    print("✅ ENHANCED DATA GENERATION COMPLETE")
    print("="*70)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
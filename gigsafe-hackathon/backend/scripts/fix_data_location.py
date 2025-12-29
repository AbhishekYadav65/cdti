# backend/scripts/fix_data_location.py
import shutil
import os

# Move files to correct location
if os.path.exists('backend/data/synthetic/drivers.csv'):
    shutil.move('backend/data/synthetic/drivers.csv', 'data/synthetic/drivers.csv')
    print("✅ Moved drivers.csv")

if os.path.exists('backend/data/synthetic/trips.csv'):
    shutil.move('backend/data/synthetic/trips.csv', 'data/synthetic/trips.csv')
    print("✅ Moved trips.csv")

print("✅ Files moved to correct location")
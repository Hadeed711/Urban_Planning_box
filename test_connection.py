#!/usr/bin/env python3
"""
🧪 Simple Earth Engine Connection Test
Quick test to verify Google Earth Engine service account is working
"""

import json
import os
import ee

def test_connection():
    """Test Earth Engine connection"""
    print("🧪 Testing Earth Engine Connection...")
    print("=" * 40)
    
    # Check service account file
    if not os.path.exists('service_account.json'):
        print("❌ service_account.json not found")
        return False
    
    try:
        # Load service account
        with open('service_account.json', 'r') as f:
            service_info = json.load(f)
        
        print(f"📧 Service Account: {service_info['client_email']}")
        
        # Initialize Earth Engine
        credentials = ee.ServiceAccountCredentials(
            service_info['client_email'], 
            'service_account.json'
        )
        ee.Initialize(credentials)
        
        # Test basic operation
        image = ee.Image("USGS/SRTMGL1_003")
        info = image.getInfo()
        
        print("✅ Earth Engine connection successful!")
        print(f"✅ Test dataset: {info['id']}")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    print("\n" + "="*40)
    if success:
        print("🎉 Ready for Streamlit deployment!")
    else:
        print("🔧 Please fix the issues above")

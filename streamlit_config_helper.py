#!/usr/bin/env python3
"""
🔧 Streamlit Cloud Configuration Helper
This script helps prepare your service account for Streamlit Cloud deployment
"""

import json
import os

def prepare_for_streamlit_cloud():
    """Prepare service account JSON for Streamlit Cloud secrets"""
    
    print("🔧 Streamlit Cloud Configuration Helper")
    print("=" * 50)
    
    # Check if service account file exists
    service_account_file = "service_account.json"
    if not os.path.exists(service_account_file):
        print(f"❌ ERROR: {service_account_file} not found")
        return False
    
    # Load the service account JSON
    try:
        with open(service_account_file, 'r') as f:
            service_account_info = json.load(f)
        print("✅ Service account JSON loaded successfully")
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON format: {e}")
        return False
    
    # Create the properly formatted JSON for Streamlit Cloud
    print("\n📋 STREAMLIT CLOUD SETUP INSTRUCTIONS:")
    print("=" * 50)
    print("1. Go to your Streamlit Cloud app settings")
    print("2. Navigate to 'Secrets' section")
    print("3. Add a new secret with key: GCP_SERVICE_ACCOUNT")
    print("4. Copy and paste the JSON below as the value:")
    print()
    print("🔑 SECRET KEY: GCP_SERVICE_ACCOUNT")
    print("📄 SECRET VALUE (copy everything between the lines):")
    print("-" * 80)
    
    # Format as compact JSON (no extra spaces)
    compact_json = json.dumps(service_account_info, separators=(',', ':'))
    print(compact_json)
    
    print("-" * 80)
    print()
    print("⚠️  IMPORTANT NOTES:")
    print("• Copy the ENTIRE JSON including the curly braces { }")
    print("• Do NOT add extra quotes around the JSON")
    print("• Do NOT modify or escape any characters")
    print("• Paste it exactly as shown above")
    print()
    print("🔐 SECURITY REMINDER:")
    print("• Never share this JSON publicly")
    print("• Only use it in Streamlit Cloud secrets")
    print("• Keep your service_account.json file secure")
    
    return True

if __name__ == "__main__":
    prepare_for_streamlit_cloud()

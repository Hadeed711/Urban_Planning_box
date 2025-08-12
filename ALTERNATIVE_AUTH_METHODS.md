# Alternative Authentication Methods for Google Earth Engine

## Method 1: Using Google Application Default Credentials (No Service Account Needed)

If you're having trouble with service account authentication, you can try these alternative methods:

### Option A: Public/Token Authentication
```python
import ee

# For public datasets only (limited functionality)
try:
    ee.Initialize()
    print("✅ Earth Engine initialized with public access")
except:
    print("❌ Public access failed")
```

### Option B: OAuth Flow (Interactive)
```python
import ee

# This will prompt for authentication in browser
try:
    ee.Authenticate()  # This opens browser for OAuth
    ee.Initialize()
    print("✅ Earth Engine initialized with OAuth")
except:
    print("❌ OAuth authentication failed")
```

### Option C: Using Google Cloud SDK Authentication
If you have Google Cloud SDK installed:
```bash
gcloud auth application-default login
```

Then in Python:
```python
import ee
from google.auth import default

credentials, project = default()
ee.Initialize(credentials)
```

## Method 2: Debugging Your Current Setup

Add this to your Streamlit app to debug what's happening:

```python
def debug_secrets():
    st.write("### 🔍 Debugging Information")
    
    # Check if secrets exist
    if hasattr(st, 'secrets'):
        st.write("✅ st.secrets is available")
        st.write(f"Available keys: {list(st.secrets.keys())}")
        
        # Check each required secret
        required_secrets = ['GOOGLE_TYPE', 'GOOGLE_PROJECT_ID', 'GOOGLE_PRIVATE_KEY_ID', 
                          'GOOGLE_PRIVATE_KEY', 'GOOGLE_CLIENT_EMAIL', 'GOOGLE_CLIENT_ID']
        
        for secret in required_secrets:
            if secret in st.secrets:
                st.write(f"✅ {secret}: Found")
            else:
                st.write(f"❌ {secret}: Missing")
    else:
        st.write("❌ st.secrets is not available")
```

## Method 3: Alternative Secret Format

Try formatting your secrets.toml file differently:

```toml
[secrets]
# Try without quotes around the keys
GOOGLE_TYPE = "service_account"
GOOGLE_PROJECT_ID = "notional-gist-467013-r5"
# ... other fields

# Or try with a different structure:
[secrets.google]
type = "service_account"
project_id = "notional-gist-467013-r5"
# ... other fields
```

## Method 4: Using Environment Variables in Streamlit Cloud

Instead of the secrets.toml format, try setting environment variables directly in Streamlit Cloud:

1. Go to your app settings
2. Add environment variables:
   - `GOOGLE_APPLICATION_CREDENTIALS_JSON`
   - Set it to your full service account JSON

Then in code:
```python
import os
import json

if 'GOOGLE_APPLICATION_CREDENTIALS_JSON' in os.environ:
    creds_json = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'])
    credentials = service_account.Credentials.from_service_account_info(creds_json)
    ee.Initialize(credentials)
```

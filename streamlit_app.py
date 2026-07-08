import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.oauth2 import service_account
from datetime import date, datetime, timedelta



# Required scope for Earth Engine
EE_SCOPE = 'https://www.googleapis.com/auth/earthengine'

# Area of Interest: Faisalabad study area (same AOI as the analysis notebook)
AOI_COORDS = [[[73.07712369059382, 31.47879088746221],
               [73.07712369059382, 31.460455497677543],
               [73.10481896529345, 31.460455497677543],
               [73.10481896529345, 31.47879088746221],
               [73.07712369059382, 31.47879088746221]]]

# Center of the AOI (used for the base map)
MAP_CENTER = [31.4696, 73.0910]

# Configure Streamlit page
st.set_page_config(
    page_title="Urban Heat Island Mapper & Mitigator",
    page_icon="🏙️",
    layout="wide"
)

# Initialize Earth Engine with service account authentication
def initialize_earth_engine():
    """Initialize Earth Engine with proper error handling"""
    try:
        # Check if we're in Streamlit Cloud environment first
        is_streamlit_cloud = False
        secrets_available = False
        
        try:
            # Safe check for secrets availability
            if hasattr(st, 'secrets') and st.secrets:
                secrets_available = True
                is_streamlit_cloud = True
            else:
                pass  # Running locally - will check for service account file
        except Exception as secret_error:
            secrets_available = False
        
        if secrets_available and 'GOOGLE_CLIENT_EMAIL' in st.secrets:
            # Method 1: Individual fields in secrets (prioritize this method)
            key_dict = {
                "type": st.secrets["GOOGLE_TYPE"],
                "project_id": st.secrets["GOOGLE_PROJECT_ID"],
                "private_key_id": st.secrets["GOOGLE_PRIVATE_KEY_ID"],
                "private_key": st.secrets["GOOGLE_PRIVATE_KEY"],
                "client_email": st.secrets["GOOGLE_CLIENT_EMAIL"],
                "client_id": st.secrets["GOOGLE_CLIENT_ID"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{st.secrets['GOOGLE_CLIENT_EMAIL'].replace('@', '%40')}",
                "universe_domain": "googleapis.com"
            }
            
            # Initialize Earth Engine with service account credentials
            credentials = service_account.Credentials.from_service_account_info(
                key_dict,
                scopes=[EE_SCOPE]
            )
            ee.Initialize(credentials)
            return True
            
        elif secrets_available and 'GCP_SERVICE_ACCOUNT' in st.secrets:
            # Method 2: Full JSON in secrets
            gcp_service_account = st.secrets["GCP_SERVICE_ACCOUNT"]
            
            if isinstance(gcp_service_account, dict):
                key_dict = gcp_service_account
            else:
                try:
                    key_dict = json.loads(gcp_service_account)
                except json.JSONDecodeError as je:
                    st.error(f"❌ JSON parsing error: {str(je)}")
                    st.error("💡 **Fix**: Check that your GCP_SERVICE_ACCOUNT secret is valid JSON")
                    return False
            
            # Validate required fields
            required_fields = [
                'type', 'project_id', 'private_key_id', 'private_key', 
                'client_email', 'client_id', 'auth_uri', 'token_uri',
                'auth_provider_x509_cert_url', 'client_x509_cert_url'
            ]
            
            missing_fields = [field for field in required_fields if field not in key_dict]
            
            if missing_fields:
                st.error("❌ Service Account JSON is incomplete!")
                st.error(f"Missing fields: {', '.join(missing_fields)}")
                st.error("💡 Download a fresh, complete service account JSON from Google Cloud Console")
                return False
            
            # Add missing fields with defaults if needed
            if 'universe_domain' not in key_dict:
                key_dict['universe_domain'] = 'googleapis.com'
            
            # Initialize Earth Engine with service account credentials
            credentials = service_account.Credentials.from_service_account_info(
                key_dict,
                scopes=[EE_SCOPE]
            )
            ee.Initialize(credentials)
            return True
            
        # Alternative Method: Try using any Google secrets with manual construction
        elif secrets_available and any(key.startswith('GOOGLE_') for key in st.secrets.keys()):
            try:
                # Manually construct service account info from any available secrets
                key_dict = {
                    "type": st.secrets.get("GOOGLE_TYPE", "service_account"),
                    "project_id": st.secrets.get("GOOGLE_PROJECT_ID"),
                    "private_key_id": st.secrets.get("GOOGLE_PRIVATE_KEY_ID"),
                    "private_key": st.secrets.get("GOOGLE_PRIVATE_KEY"),
                    "client_email": st.secrets.get("GOOGLE_CLIENT_EMAIL"),
                    "client_id": st.secrets.get("GOOGLE_CLIENT_ID"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{st.secrets.get('GOOGLE_CLIENT_EMAIL', '').replace('@', '%40')}",
                    "universe_domain": "googleapis.com"
                }
                
                # Remove None values
                key_dict = {k: v for k, v in key_dict.items() if v is not None}
                
                if len(key_dict) >= 5:  # Need at least basic credentials
                    credentials = service_account.Credentials.from_service_account_info(
                        key_dict,
                        scopes=[EE_SCOPE]
                    )
                    ee.Initialize(credentials)
                    return True
                    
            except Exception as manual_error:
                pass  # Continue to next method
            
        else:
            # Try public/default authentication first (no service account needed)
            try:
                ee.Initialize()
                return True
            except Exception as public_error:
                pass  # Continue to local file check
            
            # Fallback: Running locally with service account file
            SERVICE_ACCOUNT = 'streamlit-deploy@notional-gist-467013-r5.iam.gserviceaccount.com'
            
            # Try multiple possible paths for the service account file
            possible_paths = [
                'service_account.json',
                './service_account.json',
                os.path.join(os.path.dirname(__file__), 'service_account.json'),
                os.path.join(os.getcwd(), 'service_account.json')
            ]
            
            KEY_FILE = None
            for path in possible_paths:
                if os.path.exists(path):
                    KEY_FILE = path
                    break
            
            if not KEY_FILE:
                st.error("❌ Service account file not found")
                st.error("💡 Place service_account.json in your project directory")
                return False
                
            credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_FILE)
            ee.Initialize(credentials)
            return True

    except FileNotFoundError as fe:
        st.error(f"❌ File not found: {str(fe)}")
        return False
    except ee.EEException as ee_error:
        st.error(f"❌ Earth Engine error: {str(ee_error)}")
        return False
    except Exception as e:
        st.error(f"❌ Earth Engine initialization failed: {str(e)}")
        return False

# Initialize Earth Engine once per session (avoids a re-auth handshake on every rerun)
if 'ee_ready' not in st.session_state:
    st.session_state['ee_ready'] = initialize_earth_engine()
if not st.session_state['ee_ready']:
    st.stop()


def categorize_temp(temp):
    """Map a temperature to its heat category."""
    if temp >= 40:
        return "Extreme Heat"
    elif temp >= 35:
        return "High Heat"
    return "Moderate Heat"


@st.cache_data(ttl=1800, show_spinner=False)
def compute_live_hotspots(start_date, end_date, z_threshold, min_area_ha=0.5, max_hotspots=15):
    """
    Run the full satellite analysis pipeline live and return plain-Python results.

    Pipeline (same as the analysis notebook, with fixes):
      1. Landsat 8 + 9 Collection 2 L2 thermal imagery, cloud-masked, median composite
      2. LST converted from scaled Kelvin to Celsius
      3. Hotspots = pixels with z-score > threshold vs. the AOI mean
      4. The binary hotspot MASK is vectorized (not the continuous LST image,
         which would fragment into one polygon per distinct value)
      5. Each hotspot polygon is enriched with mean/max LST, area and
         WorldPop population exposure

    Returns a dict of picklable values so Streamlit can cache it.
    """
    aoi = ee.Geometry.Polygon(AOI_COORDS)

    def mask_clouds(image):
        # QA_PIXEL bits 0-4: fill, dilated cloud, cirrus, cloud, cloud shadow
        cloud_mask = image.select('QA_PIXEL').bitwiseAnd(int('11111', 2)).eq(0)
        return image.updateMask(cloud_mask)

    def kelvin_to_celsius(image):
        lst = image.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
        return lst.rename('LST_C').copyProperties(image, image.propertyNames())

    landsat = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'))
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt('CLOUD_COVER', 20))
        .map(mask_clouds)
    )

    scene_count = landsat.size().getInfo()
    if scene_count == 0:
        raise RuntimeError(
            "No cloud-free Landsat 8/9 scenes found for this date range. "
            "Try widening the date range (Landsat revisits every ~8 days)."
        )

    lst_median = landsat.map(kelvin_to_celsius).median().clip(aoi)

    # Combined reducers suffix output keys with the reducer name
    # (LST_C_mean / LST_C_stdDev), NOT the bare band name.
    stats = lst_median.reduceRegion(
        reducer=ee.Reducer.mean().combine(reducer2=ee.Reducer.stdDev(), sharedInputs=True),
        geometry=aoi,
        scale=30,
        maxPixels=1e13
    ).getInfo()
    lst_mean = stats.get('LST_C_mean')
    lst_std = stats.get('LST_C_stdDev')
    if lst_mean is None or lst_std is None:
        raise RuntimeError(f"Could not compute LST statistics for the AOI (got {stats}).")

    threshold_c = lst_mean + z_threshold * lst_std

    # Vectorize the binary hotspot mask so contiguous hot pixels merge into zones
    hot_mask = lst_median.gt(threshold_c).selfMask()
    vectors = hot_mask.reduceToVectors(
        geometry=aoi,
        scale=30,
        geometryType='polygon',
        eightConnected=True,
        labelProperty='zone',
        bestEffort=True,
        maxPixels=1e10
    )

    # Drop single-pixel noise before running the expensive per-feature stats
    vectors = vectors.map(lambda f: f.set('area_ha', f.geometry().area(1).divide(10000)))
    vectors = vectors.filter(ee.Filter.gte('area_ha', min_area_ha))

    pop_2020 = (
        ee.ImageCollection("WorldPop/GP/100m/pop")
        .filterBounds(aoi)
        .filterDate('2020-01-01', '2020-12-31')
        .mosaic()
        .clip(aoi)
    )

    def add_stats(feature):
        geom = feature.geometry()
        temps = lst_median.reduceRegion(
            reducer=ee.Reducer.mean().combine(reducer2=ee.Reducer.max(), sharedInputs=True),
            geometry=geom,
            scale=30,
            maxPixels=1e13
        )
        pop_sum = pop_2020.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geom,
            scale=100,
            maxPixels=1e13
        ).get('population')
        centroid = geom.centroid(1).coordinates()
        return feature.set({
            'temp': temps.get('LST_C_mean'),
            'max_temp': temps.get('LST_C_max'),
            'pop_exposed': pop_sum,
            'lng': centroid.get(0),
            'lat': centroid.get(1),
        })

    enriched = vectors.map(add_stats).sort('temp', False).limit(max_hotspots)
    features = enriched.getInfo()['features']

    hotspots = []
    for i, feat in enumerate(features, 1):
        props = feat['properties']
        temp = props.get('temp')
        if temp is None or props.get('lat') is None or props.get('lng') is None:
            continue
        hotspots.append({
            "id": i,
            "temp": round(temp, 1),
            "max_temp": round(props.get('max_temp') or temp, 1),
            "area_ha": round(props.get('area_ha') or 0, 2),
            "pop_exposed": int(props.get('pop_exposed') or 0),
            "lat": props.get('lat'),
            "lng": props.get('lng'),
            "location": f"Detected Zone {i}",
            "category": categorize_temp(temp),
        })

    # Tile URL for the live LST overlay (a string, so it caches cleanly)
    tile_url = lst_median.getMapId({
        'min': 20, 'max': 50,
        'palette': ['blue', 'cyan', 'green', 'yellow', 'orange', 'red']
    })['tile_fetcher'].url_format

    return {
        'hotspots': hotspots,
        'lst_mean': round(lst_mean, 2),
        'lst_std': round(lst_std, 2),
        'threshold_c': round(threshold_c, 2),
        'scene_count': scene_count,
        'tile_url': tile_url,
        'computed_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'params': {'start': start_date, 'end': end_date, 'z': z_threshold},
    }


# Sample fallback data, shown until a live computation is run.
# Single source of truth for both the map and the analysis panel.
SAMPLE_HOTSPOTS = [
    {"id": 1, "temp": 42.5, "area_ha": 2.5, "pop_exposed": 1500, "location": "Industrial Area", "category": "Extreme Heat", "lat": 31.465, "lng": 73.085},
    {"id": 2, "temp": 43.2, "area_ha": 3.2, "pop_exposed": 2100, "location": "Dense Residential", "category": "Extreme Heat", "lat": 31.470, "lng": 73.090},
    {"id": 3, "temp": 44.1, "area_ha": 1.2, "pop_exposed": 800, "location": "Market Area", "category": "Extreme Heat", "lat": 31.475, "lng": 73.100},
    {"id": 4, "temp": 38.8, "area_ha": 1.8, "pop_exposed": 1200, "location": "Commercial District", "category": "High Heat", "lat": 31.462, "lng": 73.092},
    {"id": 5, "temp": 37.2, "area_ha": 4.1, "pop_exposed": 2800, "location": "Mixed Development", "category": "High Heat", "lat": 31.468, "lng": 73.088},
    {"id": 6, "temp": 39.5, "area_ha": 2.2, "pop_exposed": 1600, "location": "Transport Hub", "category": "High Heat", "lat": 31.472, "lng": 73.095},
    {"id": 7, "temp": 33.1, "area_ha": 3.8, "pop_exposed": 2200, "location": "Suburban Area", "category": "Moderate Heat", "lat": 31.477, "lng": 73.082},
    {"id": 8, "temp": 34.7, "area_ha": 2.9, "pop_exposed": 1900, "location": "Educational District", "category": "Moderate Heat", "lat": 31.464, "lng": 73.098},
    {"id": 9, "temp": 32.4, "area_ha": 5.2, "pop_exposed": 3100, "location": "Green Belt Edge", "category": "Moderate Heat", "lat": 31.470, "lng": 73.102},
]

# Define interventions with Pakistani costs (PKR)
interventions = [
    {
        "type": "Street Trees",
        "cost_per_unit": 400,  # PKR per tree (as specified)
        "cooling_per_unit": 0.5,  # °C reduction per tree in 50m radius
        "unit": "tree",
        "description": "Native shade trees suitable for Faisalabad climate"
    },
    {
        "type": "Green Roof",
        "cost_per_unit": 1200,  # PKR per m² (local Pakistani rates)
        "cooling_per_unit": 0.8,  # °C per 1000 m²
        "unit": "m²",
        "description": "Extensive green roof system with native plants"
    },
    {
        "type": "Cool Roof",
        "cost_per_unit": 350,  # PKR per m² (reflective coating)
        "cooling_per_unit": 1.2,  # °C per 1000 m²
        "unit": "m²",
        "description": "White/reflective roof coating or tiles"
    },
    {
        "type": "Reflective Pavement",
        "cost_per_unit": 800,  # PKR per m²
        "cooling_per_unit": 0.6,  # °C per 1000 m²
        "unit": "m²",
        "description": "High-albedo pavement coating for roads"
    },
    {
        "type": "Urban Water Feature",
        "cost_per_unit": 2500,  # PKR per m²
        "cooling_per_unit": 1.5,  # °C per 100 m²
        "unit": "m²",
        "description": "Fountains or water channels for evaporative cooling"
    }
]

def recommend_interventions(hotspot, budget_pkr=None):
    """
    AI-powered intervention recommendations for urban heat island mitigation
    """
    area_m2 = hotspot.get('area_ha', 1) * 10000  # Convert hectares to m²
    pop = hotspot.get('pop_exposed', 0)
    
    results = []
    
    for intervention in interventions:
        # Calculate optimal units based on intervention type
        if intervention['unit'] == 'tree':
            # 1 tree per 50 m² for optimal coverage
            n_units = max(1, int(area_m2 / 50))
            coverage_area = n_units * 50
        else:
            # For area-based interventions, use percentage of total area
            coverage_percent = 0.3 if intervention['type'] == 'Green Roof' else 0.5  # 30% for green roofs, 50% for others
            n_units = int(area_m2 * coverage_percent)
            coverage_area = n_units
        
        # Calculate costs and benefits
        total_cost = n_units * intervention['cost_per_unit']
        
        # More realistic cooling calculation
        if intervention['unit'] == 'tree':
            # Each tree provides cooling in its immediate area
            cooling_effect = (n_units * intervention['cooling_per_unit'] * 50) / area_m2
        else:
            # For area-based interventions: cooling per 1000m² * covered area
            cooling_effect = (coverage_area / 1000) * intervention['cooling_per_unit']
        
        # Cap cooling effect at reasonable maximum (3°C for any single intervention)
        cooling_effect = min(cooling_effect, 3.0)
        
        # Cost-effectiveness metrics
        cost_per_degree = total_cost / max(cooling_effect, 0.1)
        cost_per_person = total_cost / max(pop, 1)

        # Efficiency in a single unit (°C per Lakh PKR) so scores are
        # comparable across interventions when ranking below
        efficiency_score = round(cooling_effect / (max(total_cost, 1) / 100000), 3)
        efficiency_unit = "°C per Lakh PKR"
        
        # Skip if over budget
        if budget_pkr and total_cost > budget_pkr:
            continue
            
        results.append({
            "type": intervention['type'],
            "description": intervention['description'],
            "n_units": n_units,
            "unit": intervention['unit'],
            "cost": int(total_cost),
            "cooling": round(cooling_effect, 2),
            "pop_benefit": int(pop),
            "cost_per_degree": int(cost_per_degree),
            "cost_per_person": int(cost_per_person),
            "efficiency_score": efficiency_score,
            "efficiency_unit": efficiency_unit,
            "coverage_area": int(coverage_area)
        })
    
    # Sort by efficiency score (°C per 1000 PKR) - higher is better
    results = sorted(results, key=lambda x: -x['efficiency_score'])
    
    return results

def create_simple_charts(recommendations):
    """Create simple, non-overlapping charts for analysis results"""
    if not recommendations:
        return None, None, None
    
    # Prepare data (top 5 recommendations only)
    top_recs = recommendations[:5]
    names = [rec['type'] for rec in top_recs]
    costs = [rec['cost'] for rec in top_recs]
    cooling = [rec['cooling'] for rec in top_recs]
    efficiency = [rec['efficiency_score'] for rec in top_recs]
    
    # Chart 1: Cost Comparison (Bar Chart)
    fig_cost = go.Figure()
    fig_cost.add_trace(go.Bar(
        x=names,
        y=costs,
        text=[f'PKR {cost:,}' for cost in costs],
        textposition='outside',
        marker_color='lightblue'
    ))
    fig_cost.update_layout(
        title='💰 Investment Required (PKR)',
        xaxis_title='Intervention Type',
        yaxis_title='Cost (PKR)',
        height=400
    )
    
    # Chart 2: Cooling Effectiveness (Bar Chart)
    fig_cooling = go.Figure()
    fig_cooling.add_trace(go.Bar(
        x=names,
        y=cooling,
        text=[f'{temp}°C' for temp in cooling],
        textposition='outside',
        marker_color='lightcoral'
    ))
    fig_cooling.update_layout(
        title='🌡️ Cooling Effectiveness',
        xaxis_title='Intervention Type',
        yaxis_title='Temperature Reduction (°C)',
        height=400
    )
    
    # Chart 3: Efficiency Comparison (Bar Chart)
    fig_efficiency = go.Figure()
    fig_efficiency.add_trace(go.Bar(
        x=names,
        y=efficiency,
        text=[f'{eff:.3f}' for eff in efficiency],
        textposition='outside',
        marker_color='lightgreen'
    ))
    fig_efficiency.update_layout(
        title='⚡ Efficiency Score',
        xaxis_title='Intervention Type',
        yaxis_title='Efficiency Score',
        height=400
    )
    
    return fig_cost, fig_cooling, fig_efficiency

def add_ee_layer(map_object, ee_image_object, vis_params, name):
    """Add Earth Engine layer to Folium map"""
    try:
        map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
        folium.raster_layers.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Map Data &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
            name=name,
            overlay=True,
            control=True
        ).add_to(map_object)
    except Exception as e:
        st.error(f"Error adding layer {name}: {str(e)}")

def create_map(hotspots, lst_tile_url=None):
    """Create the main Folium map from the given hotspot list.

    hotspots: list of dicts (live-computed or sample data)
    lst_tile_url: optional Earth Engine tile URL for the live LST overlay
    """
    m = folium.Map(location=MAP_CENTER, zoom_start=14)

    # Live LST raster overlay (only available after a live computation)
    if lst_tile_url:
        folium.raster_layers.TileLayer(
            tiles=lst_tile_url,
            attr='Map Data &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
            name='Land Surface Temperature (°C)',
            overlay=True,
            control=True,
            opacity=0.6
        ).add_to(m)

    # Study area boundary
    folium.Polygon(
        locations=[[lat, lng] for lng, lat in AOI_COORDS[0]],
        color='blue', weight=2, fill=False,
        tooltip='Study Area (AOI)'
    ).add_to(m)

    # Add temperature-coded markers
    for hotspot in hotspots:
        # Color-code by temperature category
        if hotspot["temp"] >= 40:
            color = 'darkred'
            fillColor = 'red'
            radius = 15
            category_emoji = '🔴'
        elif hotspot["temp"] >= 35:
            color = 'darkorange'
            fillColor = 'orange'
            radius = 12
            category_emoji = '🟠'
        else:  # 30-35°C
            color = 'gold'
            fillColor = 'yellow'
            radius = 10
            category_emoji = '🟡'
        
        folium.CircleMarker(
            location=[hotspot["lat"], hotspot["lng"]],
            radius=radius,
            popup=f"""
            <div style="width: 250px;">
            <b>{category_emoji} Hotspot {hotspot['id']}: {hotspot['location']}</b><br><br>
            🌡️ <b>Temperature:</b> {hotspot['temp']}°C<br>
            📏 <b>Area:</b> {hotspot['area_ha']} hectares<br>
            👥 <b>Population:</b> {hotspot['pop_exposed']:,}<br>
            ⚠️ <b>Category:</b> {hotspot['category']}<br><br>
            <i>Click 'Analyze Hotspot' in sidebar to get AI recommendations</i>
            </div>
            """,
            tooltip=f"{category_emoji} {hotspot['location']}: {hotspot['temp']}°C",
            color=color,
            fill=True,
            fillColor=fillColor,
            fillOpacity=0.8,
            weight=3
        ).add_to(m)
    
    # Add a legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px
                ">
    <p><b>🌡️ Temperature Categories</b></p>
    <p>🔴 Extreme Heat (40°C+)</p>
    <p>🟠 High Heat (35-40°C)</p>
    <p>🟡 Moderate Heat (30-35°C)</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add study area center marker
    folium.Marker(
        MAP_CENTER,
        popup="Faisalabad Study Area Center",
        tooltip="Study Area Center",
        icon=folium.Icon(color='blue', icon='info-sign')
    ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    return m

# Main Streamlit App
def main():
    st.title("🏙️ AI Urban Heat Island Mapper & Mitigator")
    st.markdown("### AI-Powered Heat Island Detection and Mitigation for Faisalabad, Pakistan")
    st.markdown("💰 **Currency:** Pakistani Rupees (PKR) | 🌳 **Tree Cost:** PKR 400 each")
    
    # Add explanatory tooltips and glossary
    with st.expander("ℹ️ Quick Guide & Glossary"):
        st.markdown("""
        **🎯 How to Use This Tool:**
        1. 📍 View the interactive map showing heat hotspots in different colors
        2. 🔍 Select a hotspot from the dropdown to analyze
        3. 💡 Click "Analyze Hotspot" to get AI-powered intervention recommendations
        4. 🧪 Use the simulator to test different intervention scenarios
        
        **📚 Key Terms:**
        - **🔥 Hotspot:** An area with significantly higher temperature than surrounding areas
        - **📏 Hectare (ha):** Unit of area = 10,000 square meters (about 2.5 acres)
        - **🌡️ LST:** Land Surface Temperature measured by satellites
        - **🌱 NDVI:** Normalized Difference Vegetation Index (measures plant health/density)
        - **🏢 LCZ:** Local Climate Zones (urban area classifications)
        - **⚡ Efficiency Score:** Temperature reduction per 1000 PKR invested
        
        **🎨 Temperature Categories:**
        - 🔴 **Extreme Heat (40°C+):** Immediate intervention needed
        - 🟠 **High Heat (35-40°C):** Priority areas for cooling
        - 🟡 **Moderate Heat (30-35°C):** Preventive measures recommended
        """)
    
    
    # Sidebar for controls
    st.sidebar.header("🎛️ Controls")
    st.sidebar.markdown("*Use these controls to customize your analysis*")

    # ---- Live satellite recomputation ----
    st.sidebar.markdown("### 🛰️ Live Satellite Analysis")
    st.sidebar.markdown("*Recompute hotspots from current Landsat 8/9 imagery*")

    today = date.today()
    date_range = st.sidebar.date_input(
        "📅 Analysis Period",
        value=(today - timedelta(days=90), today),
        max_value=today,
        help="Date range for Landsat imagery. Wider ranges give more cloud-free scenes (Landsat revisits every ~8 days)."
    )
    z_threshold = st.sidebar.slider(
        "🎚️ Hotspot Sensitivity (z-score)",
        min_value=1.0, max_value=3.0, value=1.5, step=0.1,
        help="Pixels hotter than mean + z x std-dev are flagged as hotspots. Lower = more hotspots detected."
    )

    if st.sidebar.button("🔄 Recompute Hotspots", type="primary", use_container_width=True):
        if not isinstance(date_range, tuple) or len(date_range) != 2:
            st.sidebar.error("Please select both a start and an end date.")
        else:
            start_str, end_str = str(date_range[0]), str(date_range[1])
            with st.spinner("🛰️ Fetching Landsat scenes and detecting hotspots... (30-90 s)"):
                try:
                    # Clear the cache so a re-click pulls in newly acquired scenes
                    compute_live_hotspots.clear()
                    result = compute_live_hotspots(start_str, end_str, z_threshold)
                    if result['hotspots']:
                        st.session_state['live_result'] = result
                    else:
                        st.sidebar.warning(
                            f"Analysis ran ({result['scene_count']} scenes, mean LST "
                            f"{result['lst_mean']}°C) but found no hotspot larger than "
                            f"0.5 ha at z > {z_threshold}. Try lowering the sensitivity."
                        )
                except Exception as e:
                    st.sidebar.error(f"❌ Live computation failed: {e}")

    live_result = st.session_state.get('live_result')
    if live_result and st.sidebar.button("↩️ Reset to Sample Data", use_container_width=True):
        st.session_state.pop('live_result', None)
        live_result = None

    st.sidebar.markdown("---")

    # Choose the active dataset: live satellite results or sample fallback
    if live_result:
        hotspots = live_result['hotspots']
        lst_tile_url = live_result['tile_url']
        params = live_result['params']
        st.success(
            f"🛰️ **Live satellite data** — {len(hotspots)} hotspots detected from "
            f"{live_result['scene_count']} Landsat scenes ({params['start']} → {params['end']}). "
            f"Area mean LST: {live_result['lst_mean']}°C | Hotspot threshold: "
            f"{live_result['threshold_c']}°C (z > {params['z']}) | Computed: {live_result['computed_at']}"
        )
    else:
        hotspots = SAMPLE_HOTSPOTS
        lst_tile_url = None
        st.info(
            "📊 **Showing sample demonstration data** — click **🔄 Recompute Hotspots** "
            "in the sidebar to run a live satellite analysis of current conditions."
        )

    # Temperature category status (computed from the active dataset)
    n_extreme = sum(1 for h in hotspots if h['category'] == 'Extreme Heat')
    n_high = sum(1 for h in hotspots if h['category'] == 'High Heat')
    n_moderate = sum(1 for h in hotspots if h['category'] == 'Moderate Heat')
    st.markdown(
        f"🗺️ **Map Shows:** 🔴 {n_extreme} Extreme Heat zones (40°C+) | "
        f"🟠 {n_high} High Heat zones (35-40°C) | 🟡 {n_moderate} Moderate Heat zones (<35°C)"
    )

    # Add color legend in sidebar
    st.sidebar.markdown("**🎨 Map Legend:**")
    st.sidebar.markdown("🔴 **Red Circles:** Extreme Heat (40°C+)")
    st.sidebar.markdown("🟠 **Orange Circles:** High Heat (35-40°C)")
    st.sidebar.markdown("🟡 **Yellow Circles:** Moderate Heat (30-35°C)")
    st.sidebar.markdown("---")
    
    # Analysis options
    analysis_type = st.sidebar.selectbox(
        "🔬 Analysis Type",
        ["Hotspot Detection", "Intervention Planning", "Cost-Benefit Analysis"],
        help="Choose the type of analysis you want to perform"
    )
    
    # Temperature filter
    temp_filter = st.sidebar.selectbox(
        "🌡️ Temperature Filter",
        ["All Hotspots", "Extreme Heat (40°C+)", "High Heat (35-40°C)", "Moderate Heat (30-35°C)"],
        help="Filter hotspots by temperature category"
    )
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📍 Interactive Heat Map")
        st.markdown("*Click on colored circles to see hotspot details*")
        
        # Create and display map
        m = create_map(hotspots, lst_tile_url)
        map_data = st_folium(m, width=700, height=500, returned_objects=["last_clicked"])

        # Map status computed from the active dataset
        source_label = "live satellite analysis" if live_result else "sample data"
        st.markdown(f"**🎯 Map Status:** ✅ {len(hotspots)} hotspots loaded ({source_label})")
        if n_extreme:
            st.markdown(f"- 🔴 **Red circles ({n_extreme}):** " + ", ".join(f"{h['temp']}°C" for h in hotspots if h['category'] == 'Extreme Heat'))
        if n_high:
            st.markdown(f"- 🟠 **Orange circles ({n_high}):** " + ", ".join(f"{h['temp']}°C" for h in hotspots if h['category'] == 'High Heat'))
        if n_moderate:
            st.markdown(f"- 🟡 **Yellow circles ({n_moderate}):** " + ", ".join(f"{h['temp']}°C" for h in hotspots if h['category'] == 'Moderate Heat'))

        # Check if user clicked on map
        if map_data and map_data.get('last_clicked'):
            clicked_lat = map_data['last_clicked']['lat']
            clicked_lng = map_data['last_clicked']['lng']
            st.info(f"📍 Clicked location: {clicked_lat:.4f}, {clicked_lng:.4f}")
    
    with col2:
        st.subheader("🔥 Hotspot Analysis")
        st.markdown("*Select and analyze heat island hotspots*")

        # Filter the active dataset (live or sample) by heat category
        if temp_filter == "Extreme Heat (40°C+)":
            filtered_hotspots = [h for h in hotspots if h["category"] == "Extreme Heat"]
        elif temp_filter == "High Heat (35-40°C)":
            filtered_hotspots = [h for h in hotspots if h["category"] == "High Heat"]
        elif temp_filter == "Moderate Heat (30-35°C)":
            filtered_hotspots = [h for h in hotspots if h["category"] == "Moderate Heat"]
        else:
            filtered_hotspots = hotspots

        if not filtered_hotspots:
            st.warning("No hotspots found in selected temperature range")
            filtered_hotspots = hotspots
        
        # Hotspot selection
        hotspot_options = [f"Hotspot {h['id']}: {h['location']} ({h['temp']}°C)" for h in filtered_hotspots]
        selected_hotspot_idx = st.selectbox(
            "🎯 Select Hotspot for Analysis", 
            range(len(hotspot_options)), 
            format_func=lambda x: hotspot_options[x],
            help="Choose a specific hotspot to analyze and get intervention recommendations"
        )
        
        selected_hotspot = filtered_hotspots[selected_hotspot_idx]
        
        # Display hotspot info with tooltips
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.metric("🌡️ Temperature", f"{selected_hotspot['temp']}°C", 
                     help="Current land surface temperature from satellite data")
            st.metric("📏 Area", f"{selected_hotspot['area_ha']} ha", 
                     help="Size in hectares (1 ha = 10,000 m² = 2.5 acres)")
        with col_info2:
            st.metric("👥 Population Exposed", f"{selected_hotspot['pop_exposed']:,}",
                     help="Number of people living in this heat-affected area")
            st.metric("📍 Location", selected_hotspot['location'],
                     help="Geographic area description within Faisalabad")
        
        # Category indicator
        category_color = {"Extreme Heat": "🔴", "High Heat": "🟠", "Moderate Heat": "🟡"}
        st.markdown(f"**Category:** {category_color.get(selected_hotspot['category'], '🔥')} {selected_hotspot['category']}")
        
        # Budget selector
        budget_pkr = st.selectbox(
            "💰 Budget Constraint (PKR)",
            [None, 100000, 250000, 500000, 1000000, 2000000],
            format_func=lambda x: "No Limit" if x is None else f"PKR {x:,}",
            help="Set a maximum budget to filter intervention recommendations"
        )
        
        # Analysis button
        if st.button("🔍 Analyze Hotspot", type="primary"):
            st.subheader("💡 AI Intervention Recommendations")
            
            # Generate recommendations
            recs = recommend_interventions(selected_hotspot, budget_pkr)
            
            if not recs:
                st.warning("No interventions fit within the selected budget. Try increasing the budget.")
            else:
                # Display recommendations in clean cards
                st.subheader("💡 Recommended Interventions")
                
                for i, rec in enumerate(recs):
                    with st.expander(f"#{i+1} {rec['type']} - PKR {rec['cost']:,}", expanded=(i==0)):
                        st.write(f"**Description:** {rec['description']}")
                        
                        # Create columns for better layout
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.write(f"**Units Required:** {rec['n_units']:,} {rec['unit']}")
                            st.write(f"**Coverage Area:** {rec['coverage_area']:,} m²")
                        with col_b:
                            st.write(f"**Total Cost:** PKR {rec['cost']:,}")
                            st.write(f"**Cost per Person:** PKR {rec['cost_per_person']:,.0f}")
                        with col_c:
                            st.write(f"**Cooling Effect:** {rec['cooling']}°C")
                            st.write(f"**Beneficiaries:** {rec['pop_benefit']:,}")
                        
                        # Efficiency metrics with proper units
                        st.write(f"**⚡ Efficiency:** {rec['efficiency_score']} {rec['efficiency_unit']}")
                        
                        # Implementation timeline
                        if rec['type'] == 'Street Trees':
                            timeline = "8-12 weeks (includes planting season)"
                        elif 'Roof' in rec['type']:
                            timeline = "6-10 weeks (weather dependent)"
                        else:
                            timeline = "4-8 weeks (standard implementation)"
                        
                        st.write(f"**⏰ Implementation Time:** {timeline}")
                
                # Show summary
                total_cooling = sum(r['cooling'] for r in recs[:3])
                total_cost = sum(r['cost'] for r in recs[:3])
                st.success(f"🎯 **Combined Top 3 Interventions:** {total_cooling:.1f}°C cooling for PKR {total_cost:,}")
                
                # Add charts AFTER results
                st.markdown("---")
                st.subheader("📊 Analysis Charts")
                
                # Create and display charts (one per line)
                fig_cost, fig_cooling, fig_efficiency = create_simple_charts(recs)
                
                if fig_cost:
                    st.plotly_chart(fig_cost, use_container_width=True)
                
                if fig_cooling:
                    st.plotly_chart(fig_cooling, use_container_width=True)
                
                if fig_efficiency:
                    st.plotly_chart(fig_efficiency, use_container_width=True)
    
    # Bottom section for simulation
    st.markdown("---")
    st.subheader("🧪 Intervention Impact Simulator")
    st.markdown("*Test different intervention scenarios and see projected results*")
    
    col3, col4, col5 = st.columns(3)
    
    with col3:
        st.markdown("**🛠️ Intervention Setup**")
        intervention_type = st.selectbox(
            "Intervention Type", 
            [i["type"] for i in interventions],
            help="Choose the type of cooling intervention to simulate"
        )
        coverage = st.slider(
            "Coverage (%)", 
            10, 100, 50,
            help="Percentage of the hotspot area to be covered by this intervention"
        )
        
        # Show intervention details
        selected_intervention = next(i for i in interventions if i["type"] == intervention_type)
        st.markdown(f"**Description:** {selected_intervention['description']}")
        st.markdown(f"**Unit Cost:** PKR {selected_intervention['cost_per_unit']:,} per {selected_intervention['unit']}")
    
    with col4:
        st.markdown("**📊 Estimated Impact**")
        base_cooling = selected_intervention["cooling_per_unit"]
        hotspot_area_m2 = selected_hotspot['area_ha'] * 10000
        area_covered = hotspot_area_m2 * (coverage / 100)

        # Same cooling model as the recommendation engine (capped at 3°C)
        if selected_intervention['unit'] == 'tree':
            # Trees: 1 per 50 m² of covered area
            units_needed = max(1, int(area_covered / 50))
            estimated_cost = units_needed * selected_intervention['cost_per_unit']
            estimated_cooling = base_cooling * (coverage / 100)
        else:
            # Area-based interventions: cooling per 1000 m² of covered area
            units_needed = int(area_covered)
            estimated_cost = area_covered * selected_intervention['cost_per_unit']
            estimated_cooling = (area_covered / 1000) * base_cooling
        estimated_cooling = min(estimated_cooling, 3.0)

        st.markdown(f"**Temperature Reduction**  \n{estimated_cooling:.2f}°C")
        st.markdown(f"**Estimated Cost**  \nPKR {estimated_cost:,.0f}")
        st.markdown(f"**Units Required**  \n{units_needed if selected_intervention['unit'] == 'tree' else int(area_covered):,} {selected_intervention['unit']}")
        st.markdown(f"**Cost Efficiency**  \nPKR {estimated_cost/max(estimated_cooling, 0.1):,.0f} per °C")
    
    with col5:
        st.markdown("**🚀 Run Simulation**")
        if st.button("▶️ Simulate Impact", type="secondary", help="Run the simulation to see projected results"):
            st.success("✅ Simulation complete!")
            st.balloons()
            
            # Show results
            st.markdown("**📈 Simulation Results:**")
            results_text = f"""
            - **Original temperature:** {selected_hotspot['temp']}°C
            - **After intervention:** {selected_hotspot['temp'] - estimated_cooling:.1f}°C
            - **Population benefited:** {selected_hotspot['pop_exposed']:,}
            - **Cost per person:** PKR {estimated_cost/selected_hotspot['pop_exposed']:.0f}
            - **Cost per degree cooling:** PKR {estimated_cost/max(estimated_cooling, 0.1):,.0f}
            """
            st.markdown(results_text)
            
            # Implementation card
            with st.expander("📋 Municipal Implementation Card", expanded=True):
                st.markdown(f"""
                **🏙️ FAISALABAD HEAT MITIGATION PROJECT**
                
                **📍 Project Details:**
                - Hotspot: {selected_hotspot.get('location', 'Selected Area')}
                - Area: {selected_hotspot['area_ha']} hectares ({selected_hotspot['area_ha']*10000:,.0f} m²)
                - Population: {selected_hotspot['pop_exposed']:,} people
                - Current Temperature: {selected_hotspot['temp']}°C
                
                **💡 Intervention:**
                - Type: {intervention_type}
                - Coverage: {coverage}% of hotspot area
                - Units: {units_needed if selected_intervention['unit'] == 'tree' else int(area_covered):,} {selected_intervention['unit']}
                
                **💰 Financial Analysis:**
                - Total Cost: PKR {estimated_cost:,.0f}
                - Cost per Person: PKR {estimated_cost/selected_hotspot['pop_exposed']:.0f}
                - Cost per Degree Cooling: PKR {estimated_cost/max(estimated_cooling, 0.1):,.0f}
                
                **🌡️ Expected Impact:**
                - Temperature Reduction: {estimated_cooling:.2f}°C
                - Final Temperature: {selected_hotspot['temp'] - estimated_cooling:.1f}°C
                - Cooling Efficiency: {estimated_cooling/max(estimated_cost/1000, 0.1):.3f} °C per 1000 PKR
                
                **👥 Key Stakeholders:**
                - Faisalabad Development Authority (FDA)
                - Parks & Horticulture Authority (PHA)
                - District Administration
                - Local Community Organizations
                
                **⏰ Implementation Timeline:** 
                {timeline if 'timeline' in locals() else '6-12 weeks implementation'}
                
                **📊 Success Metrics:**
                - Satellite temperature monitoring
                - Community satisfaction surveys
                - Energy consumption tracking
                - Air quality measurements
                """)
    
    # Footer with enhanced information
    st.markdown("---")
    st.markdown("**🛰️ Data Sources:** Google Earth Engine, Landsat 8/9, WorldPop, Hansen Tree Cover")
    st.markdown("**🤖 Powered by:** IBM watsonx.ai, Google Earth Engine, Streamlit")
    st.markdown("**🎯 Hackathon Goal:** Autonomous AI agents for urban heat mitigation in Pakistani cities")
    st.markdown("**📧 Contact:** For municipal partnerships and implementation support")
    st.markdown("""
    <div style="text-align: center; margin: 20px 0;">
        <a href="mailto:hadeedahmad711@gmail.com" style="text-decoration: none; background: linear-gradient(45deg, #007ACC, #0066CC); color: white; padding: 8px 16px; border-radius: 20px; margin: 0 10px; font-weight: bold;">
            📧 hadeedahmad711@gmail.com
        </a>
        <a href="mailto:hateemfarooq100@gmail.com" style="text-decoration: none; background: linear-gradient(45deg, #28A745, #20A745); color: white; padding: 8px 16px; border-radius: 20px; margin: 0 10px; font-weight: bold;">
            📧 hateemfarooq100@gmail.com
        </a>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

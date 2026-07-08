import streamlit as st
import folium
from folium.plugins import Fullscreen
from streamlit_folium import st_folium
import ee
import os
import json
import math
import plotly.graph_objects as go
from collections import Counter
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


def _haversine_m(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in metres."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def dedupe_hotspots(hotspots, min_distance_m=150):
    """Remove duplicate/overlapping hotspots.

    Two hotspots whose centroids are closer than min_distance_m are treated as
    the same heat zone; the hotter one is kept. Results are returned hottest
    first with ids renumbered 1..N.
    """
    kept = []
    for h in sorted(hotspots, key=lambda x: -x['temp']):
        if all(_haversine_m(h['lat'], h['lng'], k['lat'], k['lng']) >= min_distance_m for k in kept):
            kept.append(dict(h))
    for i, h in enumerate(kept, 1):
        h['id'] = i
    return kept


def describe_sector(lat, lng):
    """Human-readable sector name from a position inside the study area."""
    lngs = [c[0] for c in AOI_COORDS[0]]
    lats = [c[1] for c in AOI_COORDS[0]]
    fy = (lat - min(lats)) / (max(lats) - min(lats))
    fx = (lng - min(lngs)) / (max(lngs) - min(lngs))
    ns = "North" if fy > 0.62 else ("South" if fy < 0.38 else "")
    ew = "East" if fx > 0.62 else ("West" if fx < 0.38 else "")
    if ns and ew:
        return f"{ns}-{ew} Quarter"
    if ns:
        return f"{ns}ern Belt"
    if ew:
        return f"{ew}ern Corridor"
    return "City Core"


def name_hotspots(hotspots):
    """Give each detected hotspot a full, unique location name based on where
    it sits in the study area (e.g. 'North-East Quarter', 'City Core – Zone B')."""
    sectors = [describe_sector(h['lat'], h['lng']) for h in hotspots]
    totals = Counter(sectors)
    seen = Counter()
    for h, sector in zip(hotspots, sectors):
        if totals[sector] > 1:
            seen[sector] += 1
            h['location'] = f"{sector} – Zone {chr(64 + seen[sector])}"
        else:
            h['location'] = sector
    return hotspots


def implementation_timeline(intervention_type):
    """Typical implementation window for an intervention type."""
    if intervention_type == 'Street Trees':
        return "8-12 weeks (includes planting season)"
    if 'Roof' in intervention_type:
        return "6-10 weeks (weather dependent)"
    return "4-8 weeks (standard implementation)"


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
            "category": categorize_temp(temp),
        })

    # Merge near-identical detections and give each zone a real location name
    hotspots = name_hotspots(dedupe_hotspots(hotspots))

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

def _comparison_bar(names, values, texts, color, title, x_title):
    """Single-measure horizontal bar chart: sorted, direct-labeled, recessive grid.

    Backgrounds stay transparent so the chart adapts to the Streamlit theme.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    fig = go.Figure(go.Bar(
        y=[names[i] for i in order],
        x=[values[i] for i in order],
        orientation='h',
        text=[texts[i] for i in order],
        textposition='outside',
        cliponaxis=False,
        marker=dict(color=color),
        hovertemplate='%{y}: %{text}<extra></extra>',
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        height=320,
        margin=dict(l=10, r=90, t=48, b=36),
        bargap=0.42,
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(title=x_title, showgrid=True, gridcolor='rgba(128,128,128,0.18)',
                   zeroline=False, showline=False),
        yaxis=dict(showgrid=False),
    )
    return fig


def create_simple_charts(recommendations):
    """Comparison charts for the top intervention recommendations."""
    if not recommendations:
        return None, None, None

    top_recs = recommendations[:5]
    names = [rec['type'] for rec in top_recs]

    fig_cost = _comparison_bar(
        names, [rec['cost'] for rec in top_recs],
        [f"PKR {rec['cost']:,}" for rec in top_recs],
        '#2a78d6', '💰 Investment Required', 'Cost (PKR)',
    )
    fig_cooling = _comparison_bar(
        names, [rec['cooling'] for rec in top_recs],
        [f"{rec['cooling']}°C" for rec in top_recs],
        '#1baf7a', '🌡️ Cooling Effectiveness', 'Temperature Reduction (°C)',
    )
    fig_efficiency = _comparison_bar(
        names, [rec['efficiency_score'] for rec in top_recs],
        [f"{rec['efficiency_score']:.3f}" for rec in top_recs],
        '#4a3aa7', '⚡ Cooling per Lakh PKR', '°C per Lakh PKR',
    )
    return fig_cost, fig_cooling, fig_efficiency

# Marker styling per heat category: (outline, fill, radius)
CATEGORY_STYLE = {
    "Extreme Heat": {"color": "#a11212", "fill": "#e02b2b", "radius": 13},
    "High Heat":    {"color": "#b45309", "fill": "#f59e0b", "radius": 11},
    "Moderate Heat": {"color": "#a16207", "fill": "#facc15", "radius": 9},
}


def create_map(hotspots, lst_tile_url=None):
    """Create the main Folium map from the given hotspot list.

    hotspots: list of dicts (live-computed or sample data)
    lst_tile_url: optional Earth Engine tile URL for the live LST overlay
    """
    m = folium.Map(location=MAP_CENTER, zoom_start=15, tiles=None, control_scale=True)

    # Base layers: clean light map (default) + satellite imagery
    folium.TileLayer('CartoDB positron', name='🗺️ Light Map').add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics',
        name='🛰️ Satellite'
    ).add_to(m)

    # Live LST raster overlay (only available after a live computation)
    if lst_tile_url:
        folium.raster_layers.TileLayer(
            tiles=lst_tile_url,
            attr='Map Data &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
            name='🌡️ Land Surface Temperature (°C)',
            overlay=True,
            control=True,
            opacity=0.55
        ).add_to(m)

    # Study area boundary
    folium.Polygon(
        locations=[[lat, lng] for lng, lat in AOI_COORDS[0]],
        color='#2563eb', weight=2.5, dash_array='6 6', fill=False,
        tooltip='Study Area (AOI) — Faisalabad'
    ).add_to(m)

    # Hotspot markers: colored circle + always-visible name label
    for hotspot in hotspots:
        style = CATEGORY_STYLE[hotspot["category"]]
        color, fill, radius = style["color"], style["fill"], style["radius"]

        popup_html = f"""
        <div style="font-family:'Segoe UI',system-ui,sans-serif; width:260px; padding:2px;">
          <div style="background:{fill}; color:#fff; border-radius:8px 8px 0 0; padding:8px 12px;
                      font-size:14px; font-weight:700; text-shadow:0 1px 2px rgba(0,0,0,.35);">
            🔥 {hotspot['location']}
          </div>
          <div style="border:1px solid #e5e7eb; border-top:none; border-radius:0 0 8px 8px; padding:10px 12px;">
            <table style="width:100%; font-size:13px; border-collapse:collapse;">
              <tr><td style="padding:3px 0; color:#6b7280;">🌡️ Mean Temperature</td>
                  <td style="text-align:right; font-weight:700; color:{color};">{hotspot['temp']}°C</td></tr>
              <tr><td style="padding:3px 0; color:#6b7280;">📏 Area</td>
                  <td style="text-align:right; font-weight:600;">{hotspot['area_ha']} ha</td></tr>
              <tr><td style="padding:3px 0; color:#6b7280;">👥 Population Exposed</td>
                  <td style="text-align:right; font-weight:600;">{hotspot['pop_exposed']:,}</td></tr>
              <tr><td style="padding:3px 0; color:#6b7280;">⚠️ Category</td>
                  <td style="text-align:right; font-weight:600;">{hotspot['category']}</td></tr>
            </table>
            <div style="margin-top:8px; font-size:11px; color:#9ca3af; font-style:italic;">
              Select this hotspot in the analysis panel for AI recommendations
            </div>
          </div>
        </div>
        """

        folium.CircleMarker(
            location=[hotspot["lat"], hotspot["lng"]],
            radius=radius,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{hotspot['location']} — {hotspot['temp']}°C ({hotspot['category']})",
            color=color,
            fill=True,
            fillColor=fill,
            fillOpacity=0.85,
            weight=2.5
        ).add_to(m)

        # Permanent pill label with the full hotspot name (instead of a bare dot)
        label_html = (
            f'<div style="position:absolute; transform:translate(-50%, -{radius + 30}px); '
            f'white-space:nowrap; background:rgba(255,255,255,0.94); '
            f'border:1.5px solid {color}; border-radius:12px; padding:2px 9px; '
            f'font-family:\'Segoe UI\',system-ui,sans-serif; font-size:11.5px; font-weight:600; '
            f'color:#1f2937; box-shadow:0 1px 4px rgba(0,0,0,0.3); pointer-events:none;">'
            f'{hotspot["location"]} '
            f'<span style="color:{color}; font-weight:700;">{hotspot["temp"]}°C</span>'
            f'</div>'
        )
        folium.Marker(
            location=[hotspot["lat"], hotspot["lng"]],
            icon=folium.DivIcon(html=label_html, icon_size=(0, 0), icon_anchor=(0, 0))
        ).add_to(m)

    # Legend with real color swatches
    legend_html = '''
    <div style="position: fixed; bottom: 24px; left: 12px; z-index: 9999;
                background: rgba(255,255,255,0.95); border: 1px solid #d1d5db;
                border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                font-family: 'Segoe UI', system-ui, sans-serif; font-size: 12.5px;
                padding: 10px 14px; line-height: 1.9; color: #1f2937;">
      <div style="font-weight: 700; margin-bottom: 2px;">🌡️ Heat Categories</div>
      <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%;
            background:#e02b2b; border:2px solid #a11212; margin-right:7px; vertical-align:-1px;"></span>Extreme Heat (40°C+)</div>
      <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%;
            background:#f59e0b; border:2px solid #b45309; margin-right:7px; vertical-align:-1px;"></span>High Heat (35–40°C)</div>
      <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%;
            background:#facc15; border:2px solid #a16207; margin-right:7px; vertical-align:-1px;"></span>Moderate Heat (&lt;35°C)</div>
      <div style="margin-top:2px; color:#6b7280;"><span style="display:inline-block; width:16px;
            border-top:2.5px dashed #2563eb; margin-right:5px; vertical-align:3px;"></span>Study area boundary</div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    Fullscreen(position='topleft', title='Fullscreen', title_cancel='Exit fullscreen').add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    return m

# Main Streamlit App
def main():
    # Light visual polish on top of the Streamlit theme
    st.markdown("""
    <style>
      .block-container { padding-top: 1.6rem; }
      div[data-testid="stMetric"] {
          background: rgba(128, 128, 128, 0.08);
          border: 1px solid rgba(128, 128, 128, 0.20);
          border-radius: 10px;
          padding: 10px 14px;
      }
      div[data-testid="stExpander"] details {
          border-radius: 10px;
      }
    </style>
    """, unsafe_allow_html=True)

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
        - **⚡ Efficiency Score:** Temperature reduction (°C) per Lakh (100,000) PKR invested
        
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
                        # Old recommendations refer to the previous dataset
                        st.session_state.pop('analysis', None)
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
        st.session_state.pop('analysis', None)
        live_result = None

    st.sidebar.markdown("---")

    # Choose the active dataset: live satellite results or sample fallback.
    # Both paths go through dedupe_hotspots so overlapping zones are merged.
    if live_result:
        hotspots = dedupe_hotspots(live_result['hotspots'])
        lst_tile_url = live_result['tile_url']
        params = live_result['params']
        st.success(
            f"🛰️ **Live satellite data** — {len(hotspots)} hotspots detected from "
            f"{live_result['scene_count']} Landsat scenes ({params['start']} → {params['end']}). "
            f"Area mean LST: {live_result['lst_mean']}°C | Hotspot threshold: "
            f"{live_result['threshold_c']}°C (z > {params['z']}) | Computed: {live_result['computed_at']}"
        )
    else:
        hotspots = dedupe_hotspots(SAMPLE_HOTSPOTS)
        lst_tile_url = None
        st.info(
            "📊 **Showing sample demonstration data** — click **🔄 Recompute Hotspots** "
            "in the sidebar to run a live satellite analysis of current conditions."
        )

    # Headline metrics for the active dataset
    n_extreme = sum(1 for h in hotspots if h['category'] == 'Extreme Heat')
    n_high = sum(1 for h in hotspots if h['category'] == 'High Heat')
    n_moderate = sum(1 for h in hotspots if h['category'] == 'Moderate Heat')
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("🔥 Hotspots Detected", len(hotspots),
                 help=f"🔴 {n_extreme} extreme | 🟠 {n_high} high | 🟡 {n_moderate} moderate")
    mcol2.metric("🌡️ Hottest Zone", f"{max(h['temp'] for h in hotspots)}°C",
                 help="Highest mean land surface temperature among detected hotspots")
    mcol3.metric("👥 Population Exposed", f"{sum(h['pop_exposed'] for h in hotspots):,}",
                 help="Total people living inside detected heat zones (WorldPop 2020)")
    mcol4.metric("📏 Total Hot Area", f"{sum(h['area_ha'] for h in hotspots):.1f} ha",
                 help="Combined area of all detected heat zones in hectares")

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
        st.markdown("*Each labeled marker is a heat zone — click one for details, or switch to the satellite base layer*")

        # Create and display map
        m = create_map(hotspots, lst_tile_url)
        map_data = st_folium(m, height=560, use_container_width=True, returned_objects=["last_clicked"])

        source_label = "live satellite analysis" if live_result else "sample data"
        st.caption(
            f"🎯 {len(hotspots)} hotspots loaded from {source_label} — "
            f"🔴 {n_extreme} extreme · 🟠 {n_high} high · 🟡 {n_moderate} moderate"
        )

        # Check if user clicked on map
        if map_data and map_data.get('last_clicked'):
            clicked_lat = map_data['last_clicked']['lat']
            clicked_lng = map_data['last_clicked']['lng']
            st.caption(f"📍 Last clicked location: {clicked_lat:.4f}, {clicked_lng:.4f}")
    
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
        
        # Analysis button: snapshot the recommendations into session state so
        # they survive Streamlit reruns (map clicks, widget changes, etc.)
        if st.button("🔍 Analyze Hotspot", type="primary", use_container_width=True):
            st.session_state['analysis'] = {
                'hotspot': selected_hotspot,
                'budget': budget_pkr,
                'recs': recommend_interventions(selected_hotspot, budget_pkr),
            }

    # ---- AI recommendation results (full width, persistent) ----
    analysis = st.session_state.get('analysis')
    if analysis:
        st.markdown("---")
        hs = analysis['hotspot']
        recs = analysis['recs']

        header_col, clear_col = st.columns([5, 1])
        with header_col:
            st.subheader("💡 AI Intervention Recommendations")
            budget_label = "no budget limit" if analysis['budget'] is None else f"budget PKR {analysis['budget']:,}"
            st.markdown(
                f"*For **{hs['location']}** — {hs['temp']}°C · {hs['area_ha']} ha · "
                f"{hs['pop_exposed']:,} people exposed · {budget_label}*"
            )
        with clear_col:
            if st.button("✖ Clear Results", use_container_width=True):
                st.session_state.pop('analysis', None)
                st.rerun()

        if not recs:
            st.warning("No interventions fit within the selected budget. Try increasing the budget.")
        else:
            for i, rec in enumerate(recs):
                rank_badge = "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else "▫️"))
                with st.expander(f"{rank_badge} #{i+1} {rec['type']} — PKR {rec['cost']:,} · {rec['cooling']}°C cooling", expanded=(i == 0)):
                    st.write(f"**Description:** {rec['description']}")

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

                    st.write(f"**⚡ Efficiency:** {rec['efficiency_score']} {rec['efficiency_unit']}")
                    st.write(f"**⏰ Implementation Time:** {implementation_timeline(rec['type'])}")

            # Summary of the best combined package
            total_cooling = sum(r['cooling'] for r in recs[:3])
            total_cost = sum(r['cost'] for r in recs[:3])
            st.success(f"🎯 **Combined Top 3 Interventions:** {total_cooling:.1f}°C cooling for PKR {total_cost:,}")

            # Comparison charts
            st.subheader("📊 Comparison Charts")
            fig_cost, fig_cooling, fig_efficiency = create_simple_charts(recs)
            if fig_cost:
                tab_cost, tab_cool, tab_eff = st.tabs(["💰 Investment", "🌡️ Cooling", "⚡ Efficiency"])
                with tab_cost:
                    st.plotly_chart(fig_cost, use_container_width=True)
                with tab_cool:
                    st.plotly_chart(fig_cooling, use_container_width=True)
                with tab_eff:
                    st.plotly_chart(fig_efficiency, use_container_width=True)

    # Bottom section for simulation
    st.markdown("---")
    st.subheader("🧪 Intervention Impact Simulator")
    st.markdown(
        f"*Test intervention scenarios for the selected hotspot: "
        f"**{selected_hotspot['location']}** ({selected_hotspot['temp']}°C)*"
    )
    
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
        st.markdown(f"**Units Required**  \n{units_needed:,} {selected_intervention['unit']}")
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
            - **Cost per person:** PKR {estimated_cost/max(selected_hotspot['pop_exposed'], 1):,.0f}
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
                - Units: {units_needed:,} {selected_intervention['unit']}

                **💰 Financial Analysis:**
                - Total Cost: PKR {estimated_cost:,.0f}
                - Cost per Person: PKR {estimated_cost/max(selected_hotspot['pop_exposed'], 1):,.0f}
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
                {implementation_timeline(intervention_type)}
                
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

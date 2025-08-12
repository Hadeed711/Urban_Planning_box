import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configure Streamlit page
st.set_page_config(
    page_title="Urban Heat Island Mapper (Public)",
    page_icon="🏙️",
    layout="wide"
)

def initialize_earth_engine_public():
    """Initialize Earth Engine with public access only"""
    try:
        # Try public initialization (no authentication needed)
        ee.Initialize()
        st.success("✅ Earth Engine initialized with public access")
        return True
    except Exception as e:
        st.error(f"❌ Could not initialize Earth Engine: {str(e)}")
        st.error("💡 This version requires public Earth Engine access or authentication")
        return False

def create_sample_map():
    """Create a sample map with mock data when EE is not available"""
    # Sample coordinates for major Pakistani cities
    cities = {
        'Karachi': [24.8607, 67.0011],
        'Lahore': [31.5204, 74.3587],
        'Islamabad': [33.6844, 73.0479],
        'Rawalpindi': [33.5651, 73.0169],
        'Faisalabad': [31.4504, 73.1350]
    }
    
    # Create map centered on Pakistan
    m = folium.Map(location=[30.3753, 69.3451], zoom_start=6)
    
    # Add markers for major cities
    for city, coords in cities.items():
        # Simulate temperature data
        temp = 35 + (hash(city) % 10)  # Mock temperature between 35-45°C
        
        folium.CircleMarker(
            location=coords,
            radius=temp/2,
            popup=f"{city}<br>Temperature: {temp}°C",
            color='red' if temp > 40 else 'orange' if temp > 37 else 'yellow',
            fill=True,
            fillOpacity=0.6
        ).add_to(m)
    
    return m

def create_sample_charts():
    """Create sample charts with mock data"""
    # Sample temperature data
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    temperatures = [22, 25, 30, 35, 40, 42, 41, 40, 38, 33, 28, 24]
    
    # Temperature trend chart
    fig_temp = px.line(
        x=months, 
        y=temperatures,
        title="📈 Monthly Temperature Trends (Sample Data)",
        labels={'x': 'Month', 'y': 'Temperature (°C)'}
    )
    fig_temp.update_traces(line_color='red', line_width=3)
    st.plotly_chart(fig_temp, use_container_width=True)
    
    # Sample mitigation costs
    interventions = [
        'Green Roofs', 'Tree Planting', 'Cool Pavements', 
        'Water Features', 'Shade Structures'
    ]
    costs_per_sqm = [150, 50, 200, 300, 100]
    
    fig_cost = px.bar(
        x=interventions,
        y=costs_per_sqm,
        title="💰 Mitigation Intervention Costs (PKR per sq meter)",
        labels={'x': 'Intervention Type', 'y': 'Cost (PKR)'}
    )
    fig_cost.update_traces(marker_color='green')
    st.plotly_chart(fig_cost, use_container_width=True)

def main():
    st.title("🏙️ Urban Heat Island Mapper & Mitigator")
    st.markdown("### 🌡️ Climate Analysis Tool for Pakistani Cities")
    
    # Try to initialize Earth Engine
    ee_available = initialize_earth_engine_public()
    
    if not ee_available:
        st.warning("⚠️ Running in demo mode with sample data")
        st.info("💡 For live satellite data, proper authentication is required")
    
    # Sidebar
    st.sidebar.title("🎛️ Controls")
    
    # City selection
    cities = ['Karachi', 'Lahore', 'Islamabad', 'Rawalpindi', 'Faisalabad']
    selected_city = st.sidebar.selectbox("🏙️ Select City", cities)
    
    # Analysis options
    analysis_type = st.sidebar.radio(
        "📊 Analysis Type",
        ["Temperature Map", "Trend Analysis", "Mitigation Planning"]
    )
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if analysis_type == "Temperature Map":
            st.subheader(f"🗺️ Heat Map - {selected_city}")
            
            if ee_available:
                st.info("🛰️ Loading live satellite data...")
                # Here you would add actual EE code when authentication works
                st.error("Live data requires authentication - showing sample map")
            
            # Show sample map
            sample_map = create_sample_map()
            st_folium(sample_map, width=700, height=400)
            
        elif analysis_type == "Trend Analysis":
            st.subheader("📈 Temperature Trends")
            create_sample_charts()
            
        elif analysis_type == "Mitigation Planning":
            st.subheader("🌱 Mitigation Strategies")
            
            # Sample mitigation calculator
            area = st.number_input("Area to treat (sq meters)", min_value=100, max_value=10000, value=1000)
            
            st.write("### Recommended Interventions:")
            interventions = {
                'Tree Planting 🌳': {'cost': 50, 'cooling': 3},
                'Green Roofs 🏠': {'cost': 150, 'cooling': 5},
                'Cool Pavements 🛣️': {'cost': 200, 'cooling': 2},
                'Water Features 💧': {'cost': 300, 'cooling': 4}
            }
            
            for intervention, data in interventions.items():
                total_cost = area * data['cost']
                cooling_effect = data['cooling']
                
                st.write(f"**{intervention}**")
                st.write(f"- Cost: PKR {total_cost:,.0f}")
                st.write(f"- Cooling Effect: {cooling_effect}°C reduction")
                st.write("---")
    
    with col2:
        st.subheader("📊 Quick Stats")
        
        # Sample statistics
        st.metric("🌡️ Current Temp", "38°C", "2°C")
        st.metric("🔥 Heat Index", "High", "↑")
        st.metric("🌳 Green Cover", "15%", "-2%")
        st.metric("💧 Water Bodies", "8%", "0%")
        
        st.subheader("🚨 Heat Alerts")
        st.warning("⚠️ High temperature expected")
        st.info("💡 Consider indoor activities")
        
        st.subheader("📈 Recommendations")
        st.success("🌳 Increase tree cover")
        st.info("🏠 Install green roofs")
        st.warning("🛣️ Use cool pavements")

if __name__ == "__main__":
    main()

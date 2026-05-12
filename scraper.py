import pdfplumber
import pandas as pd
import requests
import io
import re
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# Initialize Geocoder (El Paso focus)
geolocator = Nominatim(user_agent="el_paso_cpc_scraper")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def extract_cpc_data(pdf_url, date):
    data_rows = []
    
    try:
        response = requests.get(pdf_url)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
            
            # Split by "Item" or "Case" - this logic varies by year, 
            # but usually, each case starts with a Case Number
            items = re.split(r'((?:PZRZ|PL|SU|ZON)\d{2}-\d{5})', full_text)
            
            for i in range(1, len(items), 2):
                case_id = items[i]
                content = items[i+1]
                
                # Regex patterns to find our dashboard fields
                location = re.search(r'Location:\s*(.*)', content)
                status = "Approved" if "Motion carried" in content or "Approved" in content else "Denied/Postponed"
                
                # Logic for Support/Opposition
                support = "Support recorded" if "in support" in content.lower() else "None recorded"
                opposition = "Opposition recorded" if "opposition" in content.lower() else "None recorded"

                data_rows.append({
                    "Date": date,
                    "Case_ID": case_id,
                    "Location": location.group(1).strip() if location else "Unknown",
                    "Status": status,
                    "Feedback": f"Support: {support} | Opp: {opposition}",
                    "Raw_Text": content[:500] # For debugging
                })
    except Exception as e:
        print(f"Error processing {pdf_url}: {e}")
        
    return data_rows

# --- THE LOOP ---
# Create a CSV named 'agenda_links.csv' with columns: 'Date' and 'Link'
links_df = pd.read_csv('agenda_links.csv')
all_results = []

print("Starting extraction...")
for index, row in links_df.iterrows():
    print(f"Processing Agenda: {row['Date']}")
    results = extract_cpc_data(row['Link'], row['Date'])
    all_results.extend(results)
    time.sleep(2) # Be polite to the city server

# Convert to DataFrame
final_df = pd.DataFrame(all_results)

# --- GEOCODING ---
print("Geocoding addresses...")
def get_coords(address):
    if address == "Unknown": return None
    # Append El Paso, TX to improve accuracy
    location = geocode(f"{address}, El Paso, TX")
    return (location.latitude, location.longitude) if location else (None, None)

final_df['Coords'] = final_df['Location'].apply(get_coords)

# Save the final dashboard data
final_df.to_csv('cpc_dashboard_data.csv', index=False)
print("Dashboard data saved to cpc_dashboard_data.csv")
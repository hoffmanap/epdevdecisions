import pdfplumber
import pandas as pd
import requests
import io
import re
import time
import bs4
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Initialize Geocoder (Focus on El Paso for better accuracy)
geolocator = Nominatim(user_agent="el_paso_cpc_scraper_hoffman")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def resolve_pdf_url(url):
    """
    Checks if the link is an HTM viewer and attempts to find the actual PDF link.
    """
    if url.lower().endswith('.htm') or 'agenda.htm' in url.lower():
        try:
            r = requests.get(url, timeout=10)
            soup = bs4.BeautifulSoup(r.text, 'html.parser')
            # Look for the first link ending in .pdf
            pdf_link = soup.find('a', href=re.compile(r'\.pdf$', re.I))
            if pdf_link:
                return requests.compat.urljoin(url, pdf_link['href'])
            else:
                # Fallback: Guess the URL by swapping extension
                return url.replace('agenda.htm', 'agenda.pdf').split('?')[0]
        except Exception as e:
            print(f"Warning: Could not resolve HTM to PDF for {url}: {e}")
            return url
    return url

def extract_cpc_data(url, date):
    data_rows = []
    target_url = resolve_pdf_url(url)
    
    print(f"--- Scraping: {target_url} ---")
    
    try:
        response = requests.get(target_url, timeout=15)
        if response.status_code != 200:
            print(f"Error: Could not download file (Status {response.status_code})")
            return []

        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
            
            # Split items based on El Paso's Case Number formats (PZRZ, PZST, PL, SU, ZON)
            items = re.split(r'((?:PZRZ|PZST|PL|SU|ZON|PWSU)\d{2}-\d{5})', full_text)
            
            # If the regex split found items, they appear in pairs (ID, Content)
            for i in range(1, len(items), 2):
                case_id = items[i]
                content = items[i+1]
                
                # Extract Location/Address
                loc_match = re.search(r'(?:Location|Property Address|Address):\s*(.*)', content, re.I)
                location = loc_match.group(1).split('\n')[0].strip() if loc_match else "Unknown"
                
                # Extract simple Status based on keywords
                status = "Approved" if any(word in content for word in ["Motion carried", "Approved", "unanimous"]) else "Check Minutes"
                
                # Extract Support/Opposition
                support_count = len(re.findall(r'support', content, re.I))
                oppose_count = len(re.findall(r'opposition|opposed', content, re.I))
                feedback = f"Mentions: Support({support_count}) Oppose({oppose_count})"

                data_rows.append({
                    "Date": date,
                    "Case_ID": case_id,
                    "Location": location,
                    "Status": status,
                    "Feedback": feedback,
                    "Source_URL": target_url
                })
                
    except Exception as e:
        print(f"Critical error parsing {target_url}: {e}")
        
    return data_rows

# --- MAIN EXECUTION LOOP ---
def main():
    try:
        # Expects a CSV with 'Date' and 'Link' columns
        links_df = pd.read_csv('agenda_links.csv')
    except FileNotFoundError:
        print("Error: 'agenda_links.csv' not found. Create it with 'Date' and 'Link' columns.")
        return

    all_results = []

    for index, row in links_df.iterrows():
        print(f"Processing Agenda Date: {row['Date']}")
        results = extract_cpc_data(row['Link'], row['Date'])
        all_results.extend(results)
        time.sleep(1) # Be kind to the city servers

    if all_results:
        final_df = pd.DataFrame(all_results)
        
        # Geocoding Step
        print("Geocoding addresses (this takes time)...")
        def get_coords(addr):
            if addr == "Unknown": return None
            try:
                # Add 'El Paso, TX' to help the geocoder find the right spot
                loc = geocode(f"{addr}, El Paso, TX")
                return (loc.latitude, loc.longitude) if loc else None
            except:
                return None

        final_df['Coordinates'] = final_df['Location'].apply(get_coords)
        
        # Save to CSV
        final_df.to_csv('cpc_dashboard_data.csv', index=False)
        print(f"Success! Saved {len(final_df)} records to 'cpc_dashboard_data.csv'")
    else:
        print("No data extracted. Check your links and regex patterns.")

if __name__ == "__main__":
    main()

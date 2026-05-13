def extract_cpc_data(url, date):
    data_rows = []
    target_url = resolve_pdf_url(url)
    print(f"--- Scraping: {target_url} ---")
    
    try:
        response = requests.get(target_url, timeout=20, headers=HEADERS)
        if response.status_code != 200: return []

        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text: full_text += text + "\n"
            
            # 1. Identify all case numbers to use as markers
            case_pattern = r'((?:PZRZ|PZST|PL|SU|ZON|PWSU|PLCP|LDC)\d{2}-\d{5})'
            markers = list(re.finditer(case_pattern, full_text))
            
            for i in range(len(markers)):
                case_id = markers[i].group(0)
                # Define the text block for this specific case
                start = markers[i].end()
                end = markers[i+1].start() if i + 1 < len(markers) else len(full_text)
                block = full_text[start:end]

                # 2. Extract Specific Dashboard Fields
                # Location
                loc_match = re.search(r'(?:Location|Property Address|Address):\s*(.*?)(?:\n[A-Z]|\n\n)', block, re.S | re.I)
                location = loc_match.group(1).replace('\n', ' ').strip() if loc_match else "Unknown"

                # Application Type & Category
                type_match = re.search(r'(?:Application Type|Request Type):\s*(.*?)\n', block, re.I)
                app_type = type_match.group(1).strip() if type_match else "See Details"

                # Request Details (Summarizes the 'Request' section)
                req_match = re.search(r'Request:\s*(.*?)(?:Staff Recommendation|Case Manager|$)', block, re.S | re.I)
                details = req_match.group(1).replace('\n', ' ').strip()[:300] + "..." if req_match else "N/A"

                # Status
                status = "Approved" if any(word in block for word in ["Motion carried", "Approved", "unanimous"]) else "Denied/Postponed"

                # Support/Opposition Summary
                support = re.findall(r'speakers? in support:?\s*(.*)', block, re.I)
                opposition = re.findall(r'speakers? in opposition:?\s*(.*)', block, re.I)
                feedback = f"Support: {len(support)} | Opp: {len(opposition)}"

                data_rows.append({
                    "Date": date,
                    "Case_ID": case_id,
                    "Location": location,
                    "Application_Type": app_type,
                    "Details": details,
                    "Status": status,
                    "Feedback": feedback,
                    "Source": target_url
                })
                
    except Exception as e:
        print(f"Error: {e}")
        
    return data_rows

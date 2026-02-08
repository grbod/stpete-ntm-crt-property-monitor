import requests
import json
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from datetime import datetime, timedelta
from airtable import Airtable
import logging
import urllib.parse
import time
import os
import traceback
from dotenv import load_dotenv

load_dotenv()

# Load credentials from environment
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')
RECIPIENT_EMAILS = [e.strip() for e in os.getenv('RECIPIENT_EMAILS', '').split(',') if e.strip()]
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME')
AIRTABLE_ACCESS_TOKEN = os.getenv('AIRTABLE_ACCESS_TOKEN')

# Set up logging configuration
logging.basicConfig(
    filename='property_matches.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s',
    filemode='a'  # Append to existing log file
)


def normalize_lot_area(entry):
    value = entry.get("lotAreaValue", 0) or 0
    unit = entry.get("lotAreaUnit", "sqft")
    if unit == "acres" or (value > 0 and value < 2):
        value = value * 43560
    return round(value)


# Function to get property data from Zillow API
def get_property_data():
    url = "https://us-housing-market-data1.p.rapidapi.com/propertyExtendedSearch"
    querystring = {
        "location": "st petersburg, fl",
        "page": "1",
        "status_type": "ForSale",
        "home_type": "Houses, Apartments, Multi-Family",
        "daysOn": "1"
    }
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "us-housing-market-data1.p.rapidapi.com"
    }

    def fetch_page(page_num):
        delays = [5, 10, 20]
        params = {**querystring, "page": str(page_num)}
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                if attempt < 2:
                    logging.warning(f'Page {page_num} attempt {attempt + 1} failed: {e}. Retrying in {delays[attempt]}s...')
                    time.sleep(delays[attempt])
                else:
                    raise RuntimeError(f'Failed to fetch page {page_num} after 3 attempts: {e}')

    data = fetch_page(1)
    total_pages = data.get('totalPages', 1)

    all_properties = data.get('props', [])
    for page in range(2, total_pages + 1):
        page_data = fetch_page(page)
        all_properties.extend(page_data.get('props', []))

    # Save the JSON data with today's date
    today_date = datetime.now().strftime("%Y-%m-%d")
    with open(f'all_property_data_{today_date}.json', 'w') as json_file:
        json.dump(all_properties, json_file)

    return all_properties

# Function to compare addresses and generate results string with additional URLs
def compare_NTMaddresses(json_data, csv_file_path):
    json_addresses = [
        {
            "address": entry.get("address", "").lower(),
            "detailUrl": "http://www.zillow.com" + entry.get("detailUrl", ""),
            "price": entry.get("price", 0),
            "lotAreaValue": normalize_lot_area(entry),
            "livingArea": entry.get("livingArea", 0),
            "imgSrc": entry.get("imgSrc", "")
        }
        for entry in json_data
    ]

    csv_addresses_df = pd.read_csv(csv_file_path)
    csv_addresses_df['Address'] = csv_addresses_df['Address'].str.lower()

    results = ""
    match_count = 0
    matched_properties = []

    for property in json_addresses:
        if any(csv_address in property['address'] for csv_address in csv_addresses_df['Address']):
            address_encoded = urllib.parse.quote(property['address'])
            ntm_map_url = f"https://egis.stpete.org/portal/apps/webappviewer/index.html?id=76797e9d8d8b4d20982cb1a2c77acd11&find={address_encoded}"
            zoning_map_url = f"https://egis.stpete.org/portal/apps/webappviewer/index.html?id=f0ff270cad0940a2879b38e955319dfa&find={address_encoded}"

            lot_area_value = property['lotAreaValue']
            if lot_area_value >= 7260:
                lot_area_formatted = f"<span style='color:green;'>{lot_area_value:,} SF</span>"
            elif 5810 <= lot_area_value < 7260:
                lot_area_formatted = f"<span style='color:orange;'>{lot_area_value:,} SF</span>"
            else:
                lot_area_formatted = f"{lot_area_value:,} SF"

            lot_price_per_sf = int(round(property['price'] / lot_area_value)) if lot_area_value > 0 else 0

            results += (
                f"<p><a href='{property['detailUrl']}'>{property['address'].capitalize()}</a></p>"
                f"<p>Price: ${property['price']:,}, Lot Size: {lot_area_formatted}, Living Area: {property['livingArea']:,} SF<br>Land Price/SF: ${lot_price_per_sf:,}/SF</p>"
                f"<img src='{property['imgSrc']}' alt='Property Image' style='width:200px; height:200px;'><br>"
                f"<p><a href='{ntm_map_url}'>NTM Map</a> | <a href='{zoning_map_url}'>Zoning Map</a></p><br><br>"
            )
            match_count += 1
            matched_properties.append({
                **property,
                "ntm_map_url": ntm_map_url,
                "zoning_map_url": zoning_map_url
            })

    results += f"<p>Total Matches Found: {match_count}</p>"
    return results, matched_properties


def capitalize_address(address):
    words = address.split()
    capitalized_words = []
    for word in words:
        if word.lower() in ['fl', 'st', 'rd', 'dr', 'ave', 'blvd', 'ln', 'pl', 'ct', 'n', 's', 'e', 'w']:
            capitalized_words.append(word.upper())
        elif word.lower() == 'saint':
            capitalized_words.append('St.')
        elif word[:-2].isdigit() and word[-2:].lower() in ['th', 'st', 'nd', 'rd']:
            capitalized_words.append(word[:-2] + word[-2:].lower())
        else:
            capitalized_words.append(word.capitalize())
    return ' '.join(capitalized_words)

def compare_HealthAddresses(json_data, csv_file_path):
    # Extract and normalize JSON addresses
    json_addresses = [
        {
            "address": entry.get("address", "").lower(),
            "core_address": " ".join(entry.get("address", "").lower().split(",")[0].split()[:3]),  # Strip to core part
            "detailUrl": "http://www.zillow.com" + entry.get("detailUrl", ""),
            "price": entry.get("price", 0),
            "lotAreaValue": normalize_lot_area(entry),
            "livingArea": entry.get("livingArea", 0),
            "imgSrc": entry.get("imgSrc", "")
        }
        for entry in json_data
    ]

    # Load and normalize CSV addresses and zones
    csv_addresses_df = pd.read_csv(csv_file_path)
    csv_addresses_df['Address'] = csv_addresses_df['Address'].str.lower()

    # Extract core addresses from CSV
    csv_addresses_df['Core_Address'] = csv_addresses_df['Address'].apply(lambda x: " ".join(x.split()[:3]))

    # Initialize results and matched properties
    results = ""
    match_count = 0
    matched_properties = []

    # Function to generate zoning map URL
    def generate_zoning_map_url(address):
        address_encoded = urllib.parse.quote(address)
        zoning_map_url = f"https://egis.stpete.org/portal/apps/webappviewer/index.html?id=f0ff270cad0940a2879b38e955319dfa&find={address_encoded}"
        return zoning_map_url

    # Define exclusion zones
    exclusion_zones = ['NTM-1', 'RC-1', 'RC-2', 'RC-3']

    # Match JSON addresses against CSV addresses
    for property in json_addresses:
        match = csv_addresses_df[(csv_addresses_df['Core_Address'] == property['core_address']) & (~csv_addresses_df['Zone_Class'].isin(exclusion_zones))]
        if not match.empty:
            zone_class = match['Zone_Class'].values[0]
            zoning_map_url = generate_zoning_map_url(property['address'])

            formatted_address = capitalize_address(property['address'])
            price_per_sf = int(round(property['price'] / property['livingArea'])) if property['livingArea'] > 0 else 0
            results += (
                f"<p><a href='{property['detailUrl']}'>{formatted_address}</a></p>"
                f"<img src='{property['imgSrc']}' alt='Property Image' style='width:200px; height:200px;'>"
                f"<p>Price: ${property['price']:,} (${price_per_sf:,}/SF)<br>Floor Area: {property['livingArea']:,} SF, Lot Size: {property['lotAreaValue']:,} SF<br>Zone: {zone_class}</p>"
                f"<p><a href='{zoning_map_url}'>Zoning Map</a></p><br><br>"
            )
            match_count += 1
            matched_properties.append({
                **property,
                "zone_class": zone_class,
                "zoning_map_url": zoning_map_url
            })

    results += f"<p>Total Matches Found: {match_count}</p>"
    return results, matched_properties

# Function to send property matches via email
def send_NTMproperty_matches(results_string, match_count):
    current_date = datetime.now().strftime("%m/%d/%y")

    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=RECIPIENT_EMAIL,
        subject=f'NTM-1 Property Matches ({match_count}) - {current_date}',
        html_content=f'''
            <h2>Matching Properties</h2>
            <p>Here are the matching properties found:</p>
            {results_string}
            <p>Thank you!</p>
            <hr>
            <h3>Cheat Sheet:</h3>
            <ul>
                <li>Min Lot SF for 5 units: <span style='color:green;'>7260 SF</span></li>
                <li>Min Lot SF for 4 units: <span style='color:orange;'>5810 SF</span></li>
                <li>Search PCPAO: <a href="https://www.pcpao.gov/quick-search?qu=1">PCPAO Quick Search</a></li>
                <li>Link to NTM ordinance: <a href="https://cms5.revize.com/revize/stpete/Business/Planning%20&%20Zoning/Land%20Development/Ord%20540-H.pdf">NTM Ordinance</a></li>
                <li>City Zoning Map: <a href="https://egis.stpete.org/portal/apps/webappviewer/index.html?id=f0ff270cad0940a2879b38e955319dfa">City Zoning Map</a></li>
                <li>NTM Zoning Map: <a href="https://egis.stpete.org/portal/apps/webappviewer/index.html?id=76797e9d8d8b4d20982cb1a2c77acd11">NTM Zoning Map</a></li>
            </ul>
        '''
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logging.info(f'Email sent: Status Code: {response.status_code}')
    except Exception as e:
        logging.error(f'Error sending email: {e}')


def send_Health_property_matches(results_string, match_count):
    current_date = datetime.now().strftime("%m/%d/%y")

    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=RECIPIENT_EMAILS,
        subject=f'Medical Office Property Matches ({match_count}) - {current_date}',
        html_content=f'''
            <h2>Matching Properties</h2>
            <p>Here are the matching properties found:</p>
            {results_string}
            <p>Thank you!</p>
            <hr>
        '''
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logging.info(f'Email sent: Status Code: {response.status_code}')
    except Exception as e:
        logging.error(f'Error sending email: {e}')


def send_error_email(error_message):
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=RECIPIENT_EMAIL,
        subject=f'Property Monitor ERROR - {datetime.now().strftime("%m/%d/%y")}',
        html_content=f'''
            <h2>Property Monitor Script Error</h2>
            <p>The property monitoring script encountered an error:</p>
            <pre>{error_message}</pre>
            <p>Please check the logs for details.</p>
        '''
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        logging.error(f'Error sending error email: {e}')


def save_daily_stats(total_scanned, ntm_matches, health_matches, ntm_properties=None, health_properties=None):
    stats_file = 'daily_stats.json'
    try:
        with open(stats_file, 'r') as f:
            stats = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        stats = []

    ntm_links = [{'address': p.get('address', ''), 'url': p.get('detailUrl', '')} for p in (ntm_properties or [])]
    health_links = [{'address': p.get('address', ''), 'url': p.get('detailUrl', '')} for p in (health_properties or [])]

    stats.append({
        'date': datetime.now().strftime('%Y-%m-%d'),
        'total_scanned': total_scanned,
        'ntm_matches': ntm_matches,
        'health_matches': health_matches,
        'ntm_links': ntm_links,
        'health_links': health_links
    })
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)


def send_weekly_summary():
    stats_file = 'daily_stats.json'
    try:
        with open(stats_file, 'r') as f:
            stats = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.info('No daily stats file found for weekly summary')
        return

    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    recent_stats = [s for s in stats if s['date'] >= week_ago]

    if not recent_stats:
        return

    rows = ""
    zero_match_days = []
    for day in recent_stats:
        rows += f"<tr><td>{day['date']}</td><td>{day['total_scanned']}</td><td>{day['ntm_matches']}</td><td>{day['health_matches']}</td></tr>"
        if day['ntm_matches'] == 0 and day['health_matches'] == 0:
            zero_match_days.append(day['date'])

    zero_match_note = ""
    if zero_match_days:
        zero_match_note = f"<p>Days with 0 matches: {', '.join(zero_match_days)}</p>"

    # Build match recap links
    match_recap = ""
    ntm_links_html = ""
    health_links_html = ""
    for day in recent_stats:
        for link in day.get('ntm_links', []):
            ntm_links_html += f"<li>{day['date']} — {capitalize_address(link['address'])} — <a href='{link['url']}'>Zillow</a></li>"
        for link in day.get('health_links', []):
            health_links_html += f"<li>{day['date']} — {capitalize_address(link['address'])} — <a href='{link['url']}'>Zillow</a></li>"

    if ntm_links_html or health_links_html:
        match_recap = "<hr><h3>All Matches This Week</h3>"
        if ntm_links_html:
            match_recap += f"<h4>NTM-1 Matches</h4><ul>{ntm_links_html}</ul>"
        if health_links_html:
            match_recap += f"<h4>Medical Office Matches</h4><ul>{health_links_html}</ul>"

    html = f'''
        <h2>Weekly Property Monitor Summary</h2>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr><th>Date</th><th>Total Scanned</th><th>NTM Matches</th><th>Health Matches</th></tr>
            {rows}
        </table>
        {zero_match_note}
        {match_recap}
    '''

    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=RECIPIENT_EMAIL,
        subject=f'Weekly Property Monitor Summary - {datetime.now().strftime("%m/%d/%y")}',
        html_content=html
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        logging.info('Weekly summary email sent')
        # Clear stats file after sending
        with open(stats_file, 'w') as f:
            json.dump([], f)
    except Exception as e:
        logging.error(f'Error sending weekly summary: {e}')


def update_NTMairtable(properties):
    # Initialize Airtable SDK
    airtable = Airtable(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, AIRTABLE_ACCESS_TOKEN)

    # Update Airtable database
    for property in properties:
        address = property.get("address", "").capitalize()
        detail_url = property.get("detailUrl", "")
        lot_size = property.get("lotAreaValue", 0)
        img_src = property.get("imgSrc", "")
        price = property.get("price", 0)
        ntm_map_url = property.get("ntm_map_url", "")
        zoning_map_url = property.get("zoning_map_url", "")

        existing = airtable.search('Name', address)
        if existing:
            logging.info(f'Skipping duplicate: {address}')
            continue

        try:
            airtable.insert({
                "Name": address,
                "URL": detail_url,
                "Lot Size": lot_size,
                "Price": price,
                "Photo": [{"url": img_src}],
                "NTM Map": ntm_map_url,
                "Zoning Map": zoning_map_url
            })
            logging.info(f'Successfully inserted: {address}')
        except Exception as e:
            logging.error(f'Error inserting {address}: {e}')


def main():
    try:
        zillow_data = get_property_data()

        NTMresults_string, NTMmatched_properties = compare_NTMaddresses(zillow_data, 'NTMaddresses.csv')
        if NTMmatched_properties:
            send_NTMproperty_matches(NTMresults_string, len(NTMmatched_properties))
            update_NTMairtable(NTMmatched_properties)
        else:
            logging.info('No NTM matches today')

        time.sleep(15)

        med_results_string, med_matched_properties = compare_HealthAddresses(zillow_data, 'HealthOfficeAddresses.csv')
        if med_matched_properties:
            send_Health_property_matches(med_results_string, len(med_matched_properties))
        else:
            logging.info('No Health matches today')

        # Save daily stats
        save_daily_stats(
            total_scanned=len(zillow_data),
            ntm_matches=len(NTMmatched_properties),
            health_matches=len(med_matched_properties),
            ntm_properties=NTMmatched_properties,
            health_properties=med_matched_properties
        )

        # Send weekly summary on Sundays
        if datetime.now().strftime('%A') == 'Sunday':
            send_weekly_summary()

    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f'Script error: {e}\n{tb}')
        send_error_email(f'{e}\n\n{tb}')


if __name__ == '__main__':
    main()

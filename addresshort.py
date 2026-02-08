import requests
import pandas as pd

def get_all_parcels_info():
    # Define the API endpoint for the Tax Parcels Info
    api_url = "https://egis.stpete.org/arcgis/rest/services/ServicesDOTS/TaxParcels/MapServer/0/query"

    # Initial parameters
    params = {
        "where": "1=1",  # This condition retrieves all records
        "outFields": "OBJECTID,ADDRESSSHORT,PARCELID",  # Fields to return
        "resultOffset": 0,  # Start at the beginning
        "resultRecordCount": 1000,  # Number of records per batch
        "f": "json",  # Response format
        "orderByFields": "OBJECTID ASC"  # Order by OBJECTID
    }

    all_data = []

    while True:
        # Make the request
        response = requests.get(api_url, params=params)
        data = response.json()

        # Append current batch of data to all_data
        all_data.extend([feature['attributes'] for feature in data['features']])

        # Check if there are more records to fetch
        if len(data['features']) < params['resultRecordCount']:
            break  # No more records to fetch

        # Update the resultOffset for the next batch
        params['resultOffset'] += params['resultRecordCount']

    # Convert to DataFrame
    parcels_df = pd.DataFrame(all_data)
    return parcels_df

def get_all_planned_redevelopment_info():
    # Define the API endpoint for the Zoning information
    api_url = "https://egis.stpete.org/arcgis/rest/services/ServicesDOTS/Zoning/MapServer/2/query"

    # Initial parameters
    params = {
        "where": "LANDUSECODE='PR-MU'",  # Filter by land use code 'PR-MU'
        "outFields": "*",  # Retrieve all fields
        "resultOffset": 0,  # Start at the beginning
        "resultRecordCount": 1000,  # Number of records per batch
        "f": "json"  # Response format
    }

    all_data = []

    while True:
        # Make the request
        response = requests.get(api_url, params=params)
        data = response.json()

        # Append current batch of data to all_data
        all_data.extend([feature['attributes'] for feature in data['features']])

        # Check if there are more records to fetch
        if len(data['features']) < params['resultRecordCount']:
            break  # No more records to fetch

        # Update the resultOffset for the next batch
        params['resultOffset'] += params['resultRecordCount']

    # Convert to DataFrame
    redevelopment_df = pd.DataFrame(all_data)
    return redevelopment_df

def main():
    # Get all parcels info
    parcels_info_df = get_all_parcels_info()

    # Get all planned redevelopment info
    redevelopment_info_df = get_all_planned_redevelopment_info()

    # Merge data on OBJECTID
    combined_data = pd.merge(redevelopment_info_df, parcels_info_df, on='OBJECTID', how='inner')

    # Print combined data
    print(combined_data)

if __name__ == "__main__":
    main()

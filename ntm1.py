from arcgis.gis import GIS
from arcgis.geocoding import reverse_geocode
from arcgis.features import FeatureLayer
import pandas as pd

# Connect to ArcGIS Online
gis = GIS()

# Define the feature layer URL
url = "https://egis.stpete.org/arcgis/rest/services/ServicesDSD/NTM/MapServer/0"

# Create a FeatureLayer object
feature_layer = FeatureLayer(url)

# Define the query parameters
query = feature_layer.query(where='1=1', out_fields='OBJECTID,Shape,TYPE,Shape_Length,Shape_Area,ACRES', return_geometry=True, result_record_count=25)

# Convert the query results to a SpatiallyEnabledDataFrame
df = query.sdf

# Select only the required columns
df = df[['OBJECTID', 'SHAPE', 'TYPE', 'Shape_Length', 'Shape_Area', 'ACRES']]

# Define the CSV file path
csv_file = 'c:/Users/greg.BODYNUTRITION/OneDrive - bodynutrition.com/Python Arcgis/NTM_1_Zoning_Specified_Fields.csv'

# Save the DataFrame to a CSV file
df.to_csv(csv_file, index=False)

# Reverse geocode the coordinates (using the centroid of each ring of the shape)
addresses = []
for index, row in df.iterrows():
    shape = row['SHAPE']
    if shape:
        rings = shape['rings']
        ring_addresses = []
        for ring in rings:
            if ring:
                centroid = ring[0]  # Get the first point of the ring as an example
                location = {'x': centroid[0], 'y': centroid[1], 'spatialReference': {'wkid': 2882}}
                result = reverse_geocode(location)
                address = result['address']['Match_addr']
                ring_addresses.append(address)
        addresses.append("; ".join(ring_addresses))  # Combine all addresses for the shape
    else:
        addresses.append(None)

df['Address'] = addresses

# Save the updated DataFrame with addresses to a CSV file
csv_file_with_addresses = 'c:/Users/greg.BODYNUTRITION/OneDrive - bodynutrition.com/Python Arcgis/NTM_1_Zoning_Specified_Fields_With_Addresses.csv'
df.to_csv(csv_file_with_addresses, index=False)

print(f"Data with addresses successfully saved to {csv_file_with_addresses}")

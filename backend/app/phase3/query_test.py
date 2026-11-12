import requests
import json

print("ENTER GRAPHQL DEPTH (e.g., 3 or 5):")
new_depth_in = input()
new_depth_val = int(new_depth_in)

print("ENTER TARGET USER TO SEARCH:")
new_user_in = input()

new_url = "http://127.0.0.1:8000/graphql_query"
new_payload = {"depth": new_depth_val, "Target_User": new_user_in}

new_response = requests.post(new_url, json=new_payload)
print(new_response.text)
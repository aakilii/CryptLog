import requests

print("ENTER ACTION (extend/remove):")
new_act = input()

new_payload = {"Lineage": "final_test_999"}

if new_act == "extend":
    new_url = "http://127.0.0.1:8000/extend"
    new_req = requests.post(new_url, json=new_payload)
    print("SERVER RESPONSE:")
    print(new_req.text)

if new_act == "remove":
    new_url = "http://127.0.0.1:8000/remove"
    new_req = requests.post(new_url, json=new_payload)
    print("SERVER RESPONSE:")
    print(new_req.text)
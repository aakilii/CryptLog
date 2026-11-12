import requests

new_url = "http://127.0.0.1:8000/phase2_webhook"

new_payload = {
    "Target_User": "admin_rahul14rx",
    "Notes": "Failed login. Attempted password: SuperSecret123! User Aadhaar is 1234-5678-9012.",
    "Lineage": "final_test_999"
}

new_req = requests.post(new_url, json=new_payload)

print("PAYLOAD FIRED:")
print(new_req.text)
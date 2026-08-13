import requests

# Example public NYC dataset endpoint so the script can be run for testing.
# Replace API_ENDPOINT and APP_TOKEN with your own values when you're ready.
API_ENDPOINT = "https://data.cityofnewyork.us/resource/43nn-pn8j.json"
APP_TOKEN = ""

headers = {
	"X-App-Token": APP_TOKEN
}

params = {
	"$limit": 50000,
	"$offset": 0
}

response = requests.get(API_ENDPOINT, headers=headers, params=params)

print(response.status_code)

with open("restaurant_data.json", "w") as f:
	f.write(response.text)

print("Finished!")


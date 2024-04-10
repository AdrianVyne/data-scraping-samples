import os
import pickle
import time
import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from bs4 import BeautifulSoup
import json
import re

DB_JSON_FILE = "initial_data_load.json"
PICKLE_TOKEN = "token.pickle"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SEARCH_QUERY = "label:weekes-forest is: unread"

# Gmail API Authentication
creds = None
if os.path.exists(PICKLE_TOKEN):
    with open(PICKLE_TOKEN, "rb") as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials-tom.json", SCOPES)
        creds = flow.run_local_server(port=0)

    with open(PICKLE_TOKEN, "wb") as token:
        pickle.dump(creds, token)

# Gmail API Service
service = build("gmail", "v1", credentials=creds)


def mark_email_as_read(service, message_id):
    # Mark the email as read by removing the "UNREAD" label
    service.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


def get_most_recent_email(service):
    # Use the correct label name or ID to fetch unread messages
    results = service.users().messages().list(userId="me", q=SEARCH_QUERY).execute()

    if "messages" in results:
        message = results["messages"][0]  # Assuming you want the most recent email
        msg = service.users().messages().get(userId="me", id=message["id"]).execute()
        payload = msg["payload"]

        # Get the body of the email
        if "parts" in payload:
            parts = payload["parts"]
            for part in parts:
                if part["mimeType"] == "text/plain":
                    body = part["body"]["data"]
                    decoded_body = base64.urlsafe_b64decode(body).decode("utf-8")
                    cleaned_body = decoded_body.replace("\r", "").replace("\n", " ")
                    print(f"Body: {decoded_body}")
                    mark_email_as_read(service, message["id"])
                    return cleaned_body
                elif part["mimeType"] == "multipart/alternative":
                    for sub_part in part["parts"]:
                        if sub_part["mimeType"] == "text/plain":
                            sub_body = sub_part["body"]["data"]
                            decoded_sub_body = base64.urlsafe_b64decode(
                                sub_body
                            ).decode("utf-8")
                            cleaned_sub_body = decoded_sub_body.replace(
                                "\r", ""
                            ).replace("\n", " ")
                            mark_email_as_read(service, message["id"])
                            return cleaned_sub_body


def extract_load_list(email_content):
    # Use regex to extract all load list sections
    load_list_matches = re.finditer(
        r"(\d{1,2}/\d{1,2}/\d{2}.+?\d{3}[\s\.-]*\d{3}[\s\.-]*\d{4}.+?)",
        email_content,
        re.DOTALL,
    )
    load_list_sections = []

    for match in load_list_matches:
        load_list_sections.append(match.group(0))

    # If the first section is too long, use a different pattern
    if load_list_sections and len(load_list_sections[0]) >= 200:
        load_list_sections = re.findall(
            r"(\d{1,2}/\d{1,2}/\d{2}[\s\S]+?MN[\s\S]+?\d{5}[\s\S]+?\d{2},\d{3}[\s\S]+?\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?[\s\S]+?(?:No|Yes|Keep dry))",
            email_content,
        )

    if load_list_sections:
        return load_list_sections
    else:
        return None


def parse_loads(email_content):
    load_list = extract_load_list(email_content)
    if load_list:
        formatted_loads = []
        for load in load_list:
            # Split the load string based on whitespace
            load_data = re.split(r'(\s+|(?<!\s)-(?!\s))', load)
            load_data = [item for item in load_data if item.strip()]

            if len(load_data) >= 9:

                # Extract fields from the split data
                date = load_data[0]
                origin_city = " ".join(load_data[3:5]).replace(".", "").replace(",", "")
                origin_state = load_data[5]
                if "steel" in load.lower():
                    commodity = "Steel"
                else:
                    commodity = "FAK"

                if len(load_data[7]) != 2:
                    destination_city = " ".join(load_data[6:8])
                    if len(load_data[9]) == 2:
                        destination_state = load_data[9]
                    else:
                        destination_state = load_data[8]
                    weight = next(
                        (
                            int(text.replace(",", ""))
                            for text in load_data
                            if text.count(",") == 1
                            and text.replace(",", "").isdigit()
                            and len(text.replace(",", "")) == 5
                        ),
                        48000,
                    )
                    rate = next(
                        (
                            text.replace("$", "").replace(",", "")
                            for text in load_data
                            if "$" in text
                        ),
                        0,
                    )
                    tarp = next(
                        (
                            text
                            for text in load_data
                            if text.lower() in ["no", "keep dry", "dry", "keep"]
                        ),
                        "no",
                    )
                    salesperson = " ".join(load_data[-3:])
                else:
                    destination_city = load_data[6]
                    destination_state = load_data[7]
                    weight = next(
                        (
                            int(text.replace(",", ""))
                            for text in load_data
                            if text.count(",") == 1
                            and text.replace(",", "").isdigit()
                            and len(text.replace(",", "")) == 5
                        ),
                        48000,
                    )
                    rate = next(
                        (
                            text.replace("$", "").replace(",", "")
                            for text in load_data
                            if "$" in text
                        ),
                        0,
                    )
                    tarp = next(
                        (
                            text
                            for text in load_data
                            if text.lower() in ["no", "keep dry", "dry", "keep"]
                        ),
                        "no",
                    )
                    salesperson = " ".join(load_data[-3:])

                formatted_load = {
                    "Date": date,
                    "Origin City": origin_city,
                    "Origin State": origin_state,
                    "Destination City": destination_city,
                    "Destination State": destination_state,
                    "Weight": weight,
                    "Rate": rate,
                    "Tarp": tarp,
                    "Commodity": commodity,
                    "Salesperson": salesperson,
                }

                formatted_loads.append(formatted_load)

        return formatted_loads
    else:
        return None


def handle_loads_DAT_format(load_data):
    db_format = []
    used_reference_ids = set()

    for load in load_data:
        # Process tarp note
        tarp_note = (
            "MUST TARP" if load["Tarp"].lower() in ["yes", "keep", "dry"] else "NO TARP"
        )

        # Calculate pickup dates
        email_date = datetime.datetime.strptime(load["Date"], "%m/%d/%y")

        rates = int(load["Rate"])
        ref_id = str(rates - 222)
        while ref_id in used_reference_ids:
            # Increment by 1 if reference ID is already used
            rates += 1
            ref_id = str(rates - 222)
        # Add generated reference ID to the used set
        used_reference_ids.add(ref_id)

        # Create structured row
        db_row = {
            "PTMX #": f"WFLR{ref_id}",
            "Orig City": load["Origin City"],
            "Orig State": load["Origin State"],
            "Dest City": load["Destination City"].replace('-','').strip(),
            "Dest State": load["Destination State"],
            "PU Window Start": email_date.strftime("%m/%d/%Y, 00:00"),
            "TL Rate (w FSC)": int(load["Rate"]),
            "Equip Type": "Flatbed",
            "Weight": int(load["Weight"]),
            "Ctrl Location Alias": "WFLR",
            "Length": 48,
            "Commodity": load["Commodity"],
            "Tarp": tarp_note,
            "Salesperson": load["Salesperson"]
        }

        db_format.append(db_row)

    return db_format


def main():
    while True:
        try:
            email = get_most_recent_email(service)
            if email is not None:

                loads = parse_loads(email)
                db_format = handle_loads_DAT_format(loads)

                with open(DB_JSON_FILE, "w") as json_file1:
                    json.dump(db_format, json_file1, indent=4)

                print("sleep 5 min")
                print("------DONE/end, repeat--------")
                time.sleep(60 * 5)
            else:
                print("No email")
                print("sleep 5 min")
                print("------DONE/end, repeat--------")
                time.sleep(60 * 5)

        except Exception as e:
            # Handle the error and print the error message
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()

import os
import pickle
import base64
import csv
import re
import datetime
import time
from datetime import timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def extract_reference_id(subject):
    pattern = r"PTMX #:\s*(\d{8})"
    match = re.search(pattern, subject, re.IGNORECASE)
    if match:
        return match.group(1)
    else:
        return ""


def get_body(message):
    if "parts" in message["payload"]:
        # Multipart message handling
        parts = message["payload"]["parts"]
        for part in parts:
            if part["mimeType"] == "text/plain":
                data = part["body"]["data"]
                return base64.urlsafe_b64decode(data).decode()
    else:
        # Single-part message handling
        body = message["payload"]["body"]
        if "data" in body:
            data = body["data"]
            return base64.urlsafe_b64decode(data).decode()
    return "No body"


def extract_value_from_subject(subject, label):
    if label == "Reference ID":
        pattern = r"PTMX #:\s*(\d+)"
        match1 = re.search(pattern, subject, re.IGNORECASE)
        if match1:
            reference_id = match1.group(1)
            return reference_id
        else:
            return ""


def extract_value_from_body(body, label):
    if label == "Pickup Earliest*":
        # Extract the Pickup Window Start date using regex pattern
        pattern = r"Pickup Window Start:\s*(\d{2}/\d{2}/\d{4})"
        match = re.search(pattern, body)
        if match:
            # Get the captured date from the regex match
            pickup_date_str = match.group(1)
            pickup_date = datetime.datetime.strptime(pickup_date_str, "%m/%d/%Y")

            # Get the current date and time
            current_datetime = datetime.datetime.now()

            # If the extracted date is in the past, change it to the current date
            if pickup_date < current_datetime:
                pickup_date = current_datetime

            # If it's Friday after 11am or on Saturday/Sunday, set the date to next Monday
            if pickup_date.weekday() >= 5 or (
                pickup_date.weekday() == 4 and pickup_date.hour >= 11
            ):
                pickup_date += datetime.timedelta(days=3)

            # Set the time to 00:00:00 to get the date only
            date_obj = pickup_date.replace(hour=0, minute=0, second=0, microsecond=0)

            origin_city = extract_value_from_body(body, "Origin City*")
            if origin_city:
                city_delays = [
                    ("baltimore", 2),
                    ("lake charles", 1),
                    ("burney", 1),
                    ("quincy", 1),
                    ("palmetto", 1),
                    ("savannah", 1),
                    ("jacksonville", 1),
                    ("guthrie", 1),
                    ("wilmington", 1),
                ]

                for city, delay in city_delays:
                    if origin_city.lower() == city:
                        date_obj += datetime.timedelta(days=delay)

                        # Check if date_obj falls on a weekend and adjust it accordingly
                        if date_obj.weekday() >= 5 or (
                            date_obj.weekday() == 4 and date_obj.hour >= 13
                        ):
                            date_obj += datetime.timedelta(days=7 - date_obj.weekday())
                        break  # Exit the loop after finding the matching city

            return date_obj.strftime("%m/%d/%Y")

    elif label == "Pickup Latest":
        pickup_earliest = extract_value_from_body(body, "Pickup Earliest*")
        if not pickup_earliest:
            # If pickup_earliest is not provided, return None as it's required for the calculation
            return None

        pickup_latest_date = datetime.datetime.strptime(
            pickup_earliest, "%m/%d/%Y"
        ).date()

        # If pickup_earliest is on Friday, set the date to the nearest Monday
        if pickup_latest_date.weekday() == 4:
            pickup_latest_date = pickup_latest_date

        # Otherwise, set the date to the nearest Friday
        else:
            days_until_friday = (4 - pickup_latest_date.weekday()) % 7
            pickup_latest_date += datetime.timedelta(days=days_until_friday)

        return pickup_latest_date.strftime("%m/%d/%Y")

    elif label == "Length (ft)*":
        pattern = r"Weight:\s*([\d.]+)"
        weight_match = re.search(pattern, body)
        if weight_match:
            weight = float(weight_match.group(1))
            if weight == 45000:
                return "53"
        return "48"
    elif label == "Weight (lbs)*":
        pattern = r"Weight:\s*([\d.]+)"
        match4 = re.search(pattern, body)
        if match4:
            weight = int(round(float(match4.group(1))))
            return f"{weight} lbs"
        else:
            return ""
    elif label == "Full/Partial*":
        pattern = r"(?i)complete"
        if re.search(pattern, body):
            return "full"
        else:
            return "partial"
    elif label == "Equipment*":
        pattern = r"Equipment:\s*(.*?)<br/>"
        match5 = re.search(pattern, body, re.IGNORECASE)
        if match5:
            equipment_value = match5.group(1).strip()
            if "FLATBED" in equipment_value or "MAXI" in equipment_value:
                return "F"
            elif re.search(r"\bvan\b", equipment_value, re.IGNORECASE):
                return "V"
            elif re.search(r"\bB-Train\b", equipment_value, re.IGNORECASE):
                return "BT"
            else:
                return equipment_value
        else:
            return ""
    elif label == "Use Private Network*":
        return ""
    elif label == "Private Network Rate":
        return ""
    elif label == "Allow Private Network Booking":
        return ""
    elif label == "Allow Private Network Bidding":
        return ""
    elif label == "Use DAT Loadboard*":
        return "yes"
    elif label == "DAT Loadboard Rate":
        pattern_spot_rate = r"Spot Rate:\s*(\d+)(?:\.\d+)"
        pattern_line_haul = r"Line Haul:\s*(\d+)(?:\.\d+)?(?:\s|USD)"
        match_spot_rate = re.search(pattern_spot_rate, body, re.IGNORECASE)
        match_line_haul = re.search(pattern_line_haul, body, re.IGNORECASE)
        if match_spot_rate or match_line_haul:
            if match_spot_rate:
                spot_rate = int(match_spot_rate.group(1))
            else:  # match_line_haul
                spot_rate = int(match_line_haul.group(1))
            if 51 <= spot_rate <= 699:
                spot_rate -= 50
            elif 700 <= spot_rate <= 1099:
                spot_rate -= 75
            elif 1100 <= spot_rate <= 2299:
                spot_rate -= 100
            elif 2300 <= spot_rate <= 3249:
                spot_rate -= 150
            elif 3250 <= spot_rate <= 3999:
                spot_rate -= 200
            elif 4000 <= spot_rate <= 4899:
                spot_rate -= 300
            elif 4900 <= spot_rate <= 5299:
                spot_rate -= 350
            elif 5300 <= spot_rate <= 6000:
                spot_rate -= 400
            return str(spot_rate)
        else:
            return ""
    elif label == "Allow DAT Loadboard Booking":
        return "no"
    elif label == "Use Extended Network":
        return "no"
    elif label == "Contact Method*":
        return ""
    elif label == "Origin City*":
        pattern = r"Origin City/State/Zip:\s*([^/]+)"
        match = re.search(pattern, body)
        if match:
            return match.group(1).strip().title()
        else:
            return ""
    elif label == "Origin State*":
        pattern = r"Origin City/State/Zip:\s*[^/]+/([^/]+)/"
        match = re.search(pattern, body)
        if match:
            return match.group(1).strip()
        else:
            return ""
    elif label == "Origin Postal Code":
        return ""
    elif label == "Destination City*":
        pattern = r"Destination City/State/Zip:\s*([^/]+)"
        match = re.search(pattern, body)
        if match:
            return match.group(1).strip().title()
        else:
            return ""
    elif label == "Destination State*":
        pattern = r"Destination City/State/Zip:\s*[^/]+/([^/]+)/"
        match = re.search(pattern, body)
        if match:
            return match.group(1).strip()
        else:
            return ""
    elif label == "Destination Postal Code":
        return ""
    elif label == "Comment":
        if "Special Instructions: Tarp" in body:
            comment = "MUST TARP - EMAIL TO BOOK: book@ . com"
        else:
            comment = "NO TARP - EMAIL TO BOOK: book@ . com"

        if "TWIC" in body:
            comment += " TWIC required"

        if "ESCORT" in body:
            if "TWIC" in comment:
                comment += " or TWIC Escort required"
            else:
                comment += " TWIC or TWIC Escort required"
        return comment
    elif label == "Commodity":
        pattern = r"Commodity:\s*(.*?)<br/>"
        match = re.search(pattern, body)
        if match:
            return match.group(1).strip()
        else:
            return ""
    else:
        return ""


def main():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials-tom.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build("gmail", "v1", credentials=creds)

    while True:
        results = (
            service.users()
            .messages()
            .list(
                userId="me",
                q="from:ops-notifications@princetontmx.com is:unread -subject:update",
                labelIds=[],
                maxResults=500,
            )
            .execute()
        )
        messages = results.get("messages", [])

        if not messages:
            print(
                "No unread OPEN BIDS messages from ops-notifications@princetontmx.com."
            )
        else:
            # Construct the file name with the formatted date and time
            file_name = f"New loads from gmail.csv"
            with open(file_name, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)

                header_row = [
                    "Pickup Earliest*",
                    "Pickup Latest",
                    "Length (ft)*",
                    "Weight (lbs)*",
                    "Full/Partial*",
                    "Equipment*",
                    "Use Private Network*",
                    "Private Network Rate",
                    "Allow Private Network Booking",
                    "Allow Private Network Bidding",
                    "Use DAT Loadboard*",
                    "DAT Loadboard Rate",
                    "Allow DAT Loadboard Booking",
                    "Use Extended Network",
                    "Contact Method*",
                    "Origin City*",
                    "Origin State*",
                    "Origin Postal Code",
                    "Destination City*",
                    "Destination State*",
                    "Destination Postal Code",
                    "Comment",
                    "Commodity",
                    "Reference ID",
                ]
                writer.writerow(header_row)

                reference_id_worked_on = (
                    False  # Flag to track if a reference ID was worked on
                )

                for message in messages:
                    msg = (
                        service.users()
                        .messages()
                        .get(userId="me", id=message["id"])
                        .execute()
                    )
                    headers = msg["payload"]["headers"]
                    subject = next(
                        h["value"] for h in headers if h["name"] == "Subject"
                    )
                    body = get_body(msg)
                    origin_city = extract_value_from_body(body, "Origin City*")
                    if origin_city.lower() == "detroit":
                        print("Ignoring email with Origin City: Detroit")
                        continue
                    if origin_city.lower() == "big river":
                        print("Ignoring email with Origin City: Big River/ Canada")
                        continue
                    if origin_city.lower() == "grande cache":
                        print("Ignoring email with Origin City: Grande Cache/ Canada")
                        continue
                    if origin_city.lower() == "prince george":
                        print("Ignoring email with Origin City: Prince George/ Canada")
                        continue
                    pickup_earliest = extract_value_from_body(body, "Pickup Earliest*")
                    pickup_latest = extract_value_from_body(body, "Pickup Latest")
                    length = extract_value_from_body(body, "Length (ft)*")
                    weight = extract_value_from_body(body, "Weight (lbs)*")
                    full_partial = extract_value_from_body(body, "Full/Partial*")
                    equipment = extract_value_from_body(body, "Equipment*")
                    use_private_network = extract_value_from_body(
                        body, "Use Private Network*"
                    )
                    private_network_rate = extract_value_from_body(
                        body, "Private Network Rate"
                    )
                    allow_private_network_booking = extract_value_from_body(
                        body, "Allow Private Network Booking"
                    )
                    allow_private_network_bidding = extract_value_from_body(
                        body, "Allow Private Network Bidding"
                    )
                    use_dat_loadboard = extract_value_from_body(
                        body, "Use DAT Loadboard*"
                    )
                    dat_loadboard_rate = extract_value_from_body(
                        body, "DAT Loadboard Rate"
                    )
                    allow_dat_loadboard_booking = extract_value_from_body(
                        body, "Allow DAT Loadboard Booking"
                    )
                    use_extended_network = extract_value_from_body(
                        body, "Use Extended Network"
                    )
                    contact_method = extract_value_from_body(body, "Contact Method*")
                    origin_state = extract_value_from_body(body, "Origin State*")
                    origin_postal_code = extract_value_from_body(
                        body, "Origin Postal Code"
                    )
                    destination_city = extract_value_from_body(
                        body, "Destination City*"
                    )
                    destination_state = extract_value_from_body(
                        body, "Destination State*"
                    )
                    destination_postal_code = extract_value_from_body(
                        body, "Destination Postal Code"
                    )
                    comment = extract_value_from_body(body, "Comment")
                    commodity = extract_value_from_body(body, "Commodity")
                    reference_id = extract_value_from_subject(subject, "Reference ID")

                    # Check if dat_loadboard_rate is None and skip processing the email
                    if dat_loadboard_rate == "":
                        print(f"Error: No rate found for reference ID: {reference_id}")
                        continue

                    # Write the extracted values to the CSV file
                    row_data = [
                        pickup_earliest,
                        pickup_latest,
                        length,
                        weight,
                        full_partial,
                        equipment,
                        use_private_network,
                        private_network_rate,
                        allow_private_network_booking,
                        allow_private_network_bidding,
                        use_dat_loadboard,
                        dat_loadboard_rate,
                        allow_dat_loadboard_booking,
                        use_extended_network,
                        contact_method,
                        origin_city,
                        origin_state,
                        origin_postal_code,
                        destination_city,
                        destination_state,
                        destination_postal_code,
                        comment,
                        commodity,
                        reference_id,
                    ]
                    # mark emails as read
                    msg_id = message["id"]
                    service.users().messages().modify(
                        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
                    ).execute()
                    writer.writerow(row_data)
                    print(f"Worked on Reference ID: {reference_id}")
                    reference_id_worked_on = True

            print("Done exporting csv")
            print("--------")
            csvfile.close()

            if reference_id_worked_on:
                # Set up the Chrome driver
                driver = webdriver.Chrome()
                # Open the website
                driver.maximize_window()
                driver.get("https://one.dat.com/")

                # # Wait for the page to load
                # time.sleep(5)  # Adjust the delay if needed

                # Enter login credentials
                email_input = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.ID, "mat-input-1"))
                )
                email_input.send_keys("ENTER YOUR DAT ACCOUNT EMAIL")

                password_input = driver.find_element(By.ID, "mat-input-0")
                password_input.send_keys("ENTER YOUR DAT ACCOUNT PASSWORD")

                # Click the login button
                login_button = driver.find_element(
                    By.XPATH, '//button[@id="submit-button"]'
                )
                login_button.click()

                # Check for login anyway and close the pop-up if it appears
                try:
                    dialog_container = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (
                                By.XPATH,
                                '//mat-dialog-container[.//span[contains(text(), "LOGIN ANYWAY")]]',
                            )
                        )
                    )
                    login_anyway_button = dialog_container.find_element(
                        By.XPATH, './/button[span[contains(text(), "LOGIN ANYWAY")]]'
                    )
                    login_anyway_button.click()
                except:
                    pass
 
                # Go to the upload page
                driver.get("https://one.dat.com/my-shipments/forms/new-bulk-upload")
                # Check for login anyway and close the pop-up if it appears

                try:
                    # Wait for the SVG element to be clickable
                    close_button = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//div[@class='css-1o6lkht eo30uvs4']")
                        )
                    )
                    close_button.click()
                except:
                    pass

                try:
                    dialog_container = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (
                                By.XPATH,
                                '//mat-dialog-container[.//span[contains(text(), "LOGIN ANYWAY")]]',
                            )
                        )
                    )
                    login_anyway_button = dialog_container.find_element(
                        By.XPATH, './/button[span[contains(text(), "LOGIN ANYWAY")]]'
                    )
                    login_anyway_button.click()
                except:
                    pass
                # Find the file input element
                file_input = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
                )

                # Get the absolute file path of the New loads from gmail.csv file
                file_path = os.path.abspath("New loads from gmail.csv")

                # Set the file path to the file input element
                file_input.send_keys(file_path)
                # Check for login anyway and close the pop-up if it appears
                # Wait for the upload button to be clickable
                upload_button = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            'button.mat-flat-button[type="button"][color="primary"]',
                        )
                    )
                )
                upload_button.click()
                # Check for login anyway and close the pop-up if it appears
                try:
                    dialog_container = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (
                                By.XPATH,
                                '//mat-dialog-container[.//span[contains(text(), "LOGIN ANYWAY")]]',
                            )
                        )
                    )
                    login_anyway_button = dialog_container.find_element(
                        By.XPATH, './/button[span[contains(text(), "LOGIN ANYWAY")]]'
                    )
                    login_anyway_button.click()
                except:
                    pass
                # Click the post button
                post_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            'button.mat-flat-button[color="primary"][e2e="post-button"]',
                        )
                    )
                )
                post_button.click()

                # Check if there is a done button or a skip errors and close button
                try:
                    done_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, 'button.mat-flat-button[e2e="done"]')
                        )
                    )
                    done_button.click()
                except:
                    skip_errors_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, 'button[e2e="skip-errors-and-close"]')
                        )
                    )
                    skip_errors_button.click()

                    # Click the "YES" button
                    yes_button = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "button.complete.mat-flat-button")
                        )
                    )
                    yes_button.click()

                driver.quit()
                print("done uploading new CSV to DAT")
                time.sleep(5)

        break


if __name__ == "__main__":
    main()
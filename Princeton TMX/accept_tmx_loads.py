import os
import time
import json
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options

location_sets = [
    {
        'Orig City': 'CAPE CANAVERAL',
        'Orig State': 'FL',
        'Dest City': 'KISSIMMEE',
        'Dest State': 'FL',
        "TL Rate (w FSC)": 450
    }
    # Add more location sets as needed
]

# Initialize dictionary to store reference numbers for each location set
location_refnums = {tuple(loc.items()): set() for loc in location_sets}

used_ptmx_numbers = set()
def login(driver):
    try:
        driver.get("https://fctg.tmx.princetontmx.com/#/login")
        driver.maximize_window()
        username_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        username_input.send_keys("ENTER YOUR EMAIL ADDRESS HERE")
        password_input = driver.find_element(By.ID, "password")
        password_input.send_keys("ENTER YOUR PASSWROD HERE")
        sign_in_button = driver.find_element(By.XPATH, '//button[contains(., "Sign in")]')
        sign_in_button.click()
        time.sleep(10)
    except Exception as e:
        print(f"Error during login: {e}")

def setup_driver():
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--disable-gpu")
    chrome_prefs = {
        "download.default_directory": os.path.dirname(os.path.abspath(__file__)),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    chrome_options.add_experimental_option("prefs", chrome_prefs)

    driver = webdriver.Chrome(options=chrome_options)
    return driver

def navigate_to_url(driver, url):
    try:
        driver.get(url)
    except Exception as e:
        print(f"Error navigating to URL: {url}. Error: {e}")

def scroll_to_right(driver):
    try:
        scroll_container = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[@class="ag-body-horizontal-scroll-viewport"]')
            )
        )
        driver.execute_script(
            "arguments[0].scrollLeft = arguments[0].scrollWidth", scroll_container
        )
    except Exception as e:
        print(f"Error during scrolling: {e}")

def get_next_weekday(date):
    while date.weekday() >= 5:  # Check if it's Saturday (5) or Sunday (6)
        date += timedelta(days=1)
    return date

def enter_reference_number_and_accept_load(driver, refnum):
    time.sleep(3)
    input_element = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, '//input[contains(@class, "ag-input-field-input") and contains(@aria-label, "PTMX # Filter Input")]')
        )
    )

    input_element.send_keys(refnum)
    time.sleep(1)
    actions = ActionChains(driver)
    actions.send_keys(Keys.TAB).send_keys(Keys.TAB).send_keys(Keys.SPACE).perform()
    time.sleep(2)

    accept_buttons = WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, 'tmx-header-button'))
    )
    if accept_buttons:
        accept_buttons[1].click()
    else:
        print("Accept button not found")

    # Retrieve both now_buttons and their associated input_elements
    now_buttons = WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.XPATH, '//button[@type="button" and @aria-label="Set Date To Now" and span/span[contains(text(), "Now")]]'))
    )
    input_elements_xpath = "//input[contains(@class, 'mat-datepicker-input date-input ng-untouched ng-pristine ng-valid')]"
    input_elements = WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.XPATH, input_elements_xpath))
    )
    prev_date = None
    for i in range(len(now_buttons)):
        now_buttons[i].click()
        time.sleep(1)  # Wait for the date picker to update

        # Interact with the corresponding input_element
        input_element = input_elements[i]
        current_date_str = input_element.get_attribute('value')
        current_date = datetime.strptime(current_date_str, '%m/%d/%Y')
        
        # Add 2 days for the first button/input pair, 4 days for the second
        add_days = 2 if i == 0 else 4
        new_date = current_date + timedelta(days=add_days)
        new_date = get_next_weekday(new_date)
        if prev_date and new_date == prev_date:
            new_date += timedelta(days=2)
        new_date_str = new_date.strftime('%m/%d/%Y')

        # Update the date in the input field
        driver.execute_script(f"arguments[0].value='{new_date_str}';", input_element)
        print(f"Updated input value for button {i+1}: {new_date_str}")
        time.sleep(1)
        prev_date = new_date
        
    try:
        #click submit to accept the load
        submit_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CLASS_NAME, 'mat-stroked-button'))
        )
        submit_button.click()
            
        print("Accepted load")
    
    except Exception as e:
        print(f"Error during accepting load: {e}")

def check_json_changes():

    # Load existing PTMX numbers
    existing_ptmx_numbers = load_used_ptmx_numbers()

    while True:
        try:
            # Try to load existing PTMX numbers
            with open('TMX loads.json', 'r') as file:
                data = json.load(file)
            break  # Break the loop if successfully loaded without errors
        except json.decoder.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)
        except FileNotFoundError:
            print("JSON file not found. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

    for loc_set in location_sets:
        orig_city = loc_set['Orig City']
        orig_state = loc_set['Orig State']
        dest_city = loc_set['Dest City']
        dest_state = loc_set['Dest State']
        min_tl_rate = loc_set["TL Rate (w FSC)"]  # Minimum TL Rate allowed

        for entry in data:
            refnum = entry.get('PTMX #')
            tl_rate = entry.get('TL Rate (w FSC)', 0)  # Fetch TL Rate, default to 0 if not present

            # Check if the entry matches the criteria, considering empty fields in location_sets
            if (
                (not orig_city or entry.get('Orig City') == orig_city) and
                (not orig_state or entry.get('Orig State') == orig_state) and
                (not dest_city or entry.get('Dest City') == dest_city) and
                (not dest_state or entry.get('Dest State') == dest_state) and
                (tl_rate >= min_tl_rate) and
                (refnum not in existing_ptmx_numbers)
            ):
                used_ptmx_numbers.add(refnum)
                location_refnums[tuple(loc_set.items())].add(refnum)
                with open('used_locations.json', 'a') as log_file:
                    log_entry = {
                        'Orig City': orig_city,
                        'Orig State': orig_state,
                        'Dest City': dest_city,
                        'Dest State': dest_state,
                        'PTMX #': refnum
                    }
                    log_file.write(json.dumps(log_entry) + ',\n')

def handle_refnum(refnum):
    try:
        # Setup WebDriver and perform actions on web page
        driver = webdriver.Chrome()
        login(driver)
        navigate_to_url(driver, "https://fctg.tmx.princetontmx.com/#/carrierWeb/spot-rate-load-board/requests")
        scroll_to_right(driver)
        enter_reference_number_and_accept_load(driver, refnum)
        time.sleep(30)
    finally:
        driver.quit()

def load_used_ptmx_numbers():
    try:
        with open('used_location.json', 'r') as file:
            data = file.read()
            json_data = [json.loads(line) for line in data.splitlines()]
            ptmx_numbers = {entry.get('PTMX #') for entry in json_data}
            return ptmx_numbers
    except FileNotFoundError:
        return set()

def main():
    global used_ptmx_numbers
    used_ptmx_numbers = load_used_ptmx_numbers()
    handle_count = 1  # Initialize handle count
    while True:
        try:
            check_json_changes()
            print("Current time:", datetime.now().time())
            # Check if there are REFNUMs to process
            if used_ptmx_numbers:
                for refnum in used_ptmx_numbers.copy():  # Use copy to avoid modifying the set while iterating
                    print(f"Current REFNUMs: {used_ptmx_numbers}")
                    handle_refnum(refnum)
                    used_ptmx_numbers.remove(refnum)  # Remove processed REFNUM from the set
                    handle_count += 1  # Increment handle count

                    if handle_count >= 2:
                        break  # Break the loop after handle_refnum has been done twice

                if handle_count >= 2:
                    break  # Break the outer loop if handle count reaches 2
            else:
                time.sleep(5)
        except:
            print("error will try again")

if __name__ == "__main__":
    main()

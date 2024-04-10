import os
import glob
import shutil
import json
import datetime
import pandas as pd
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

logging.basicConfig(filename="TMX_app.log", level=logging.INFO)

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_prefs = {
        "download.default_directory": os.path.dirname(os.path.abspath(__file__)),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    chrome_options.add_experimental_option("prefs", chrome_prefs)

    driver = webdriver.Chrome(options=chrome_options)
    return driver

def login(driver):
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

def download_and_process_data(driver):
    try:
        driver.get(
            "https://fctg.tmx.princetontmx.com/#/carrierWeb/spot-rate-load-board/requests"
        )
        zoom_level = 67
        driver.execute_script(f"document.body.style.zoom = '{zoom_level}%'")
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CLASS_NAME, "ag-center-cols-container"))
        )
        current_datetime = datetime.datetime.now()
        formatted_datetime = current_datetime.strftime("%m-%d-%Y %H:%M:%S")
        print("------------------------------------------")
        print("Formatted Date and Time:", formatted_datetime)
        print("------------------------------------------")

        WebDriverWait(driver, 99).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    '//div[contains(@class, "ag-header-cell") and @aria-colindex="3"]',
                )
            )
        )
        button = WebDriverWait(driver, 4).until(
            EC.presence_of_element_located(
                (
                    By.CLASS_NAME,
                    "btn.md-btn.white.no-radius._600.tmx-header-button.right.ng-star-inserted",
                )
            )
        )
        driver.execute_script("arguments[0].scrollIntoView();", button)
        driver.execute_script("arguments[0].click();", button)
        print("button clicked")
        time.sleep(2)
        download_directory = os.path.dirname(os.path.abspath(__file__))
        downloaded_files = glob.glob(os.path.join(download_directory, "*.xlsx"))
        latest_downloaded_file = max(downloaded_files, key=os.path.getctime)

        new_file_name = "TMX loads.xlsx"
        new_file_path = os.path.join(download_directory, new_file_name)

        shutil.move(latest_downloaded_file, new_file_path)

        xlsx_file_path = os.path.join(download_directory, "TMX loads.xlsx")
        df = pd.read_excel(xlsx_file_path)
        json_data = df.to_json(orient="records")
        json_data = json_data.replace("\\/", "/")
        parsed_json = json.loads(json_data)
        if len(parsed_json) > 7:
            json_file_path = os.path.join(download_directory, "TMX loads.json")
            with open(json_file_path, "w") as json_file:
                json_file.write(json_data)
            print("JSON file has been created successfully.")
            print(f"Number of loads found at TMX website {len(parsed_json)}")
            time.sleep(5)
            driver.refresh()

        else:
            print("JSON file has failed.")
            print(f"Number of loads found at TMX website {len(parsed_json)}")
            time.sleep(5)
            driver.quit()

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

def run_script():
    try:
        driver = setup_driver()
        login(driver)

        while True:
            download_and_process_data(driver)
            time.sleep(5)

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    run_script()

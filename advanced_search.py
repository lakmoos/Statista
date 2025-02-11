import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlencode
import time
import os
import glob
import shutil

# Import existing functions
from scraper import setup_driver, login_with_selenium, log

SOURCE_FOLDER = os.path.abspath("statista_data")

# Define the base URL for Statista because, apparently, hardcoding is still cool sometimes
BASE_URL = "https://www.statista.com/studies-and-reports/all-reports"
failed_reports = 0


def construct_url(topic=None, page=1):
    """
    Construct the dynamic URL based on the provided topic and page number.
    If no topic is provided, return the default page URL.
    """
    params = {
        "idCountry": 0,
        "idBranch": 0,
        "idLanguage": 0,
        "reportType": 0,
        "documentTypes[]": "xls",
        "sortMethod": "idRelevance",
        "p": page,  # page
    }
    if topic:
        params["q"] = topic.replace(" ", "+")
    return f"{BASE_URL}?{urlencode(params)}"


def extract_report_results(driver, topic):
    """Extract and display report results with title, URL, and published date."""
    log.info(f'🔍 2/2 Searching for reports related to: "{topic}"...')
    reports = []
    try:
        total_results = 0
        page = 1

        while True:
            # Construct the URL for the current page
            page_url = construct_url(topic, page)
            log.info(f"   Navigating to page {page}")
            driver.get(page_url)

            # Try to load the report results; exit if no results are found
            try:
                results = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "reportResult"))
                )
            except Exception:
                log.info(f"   ⚠️ No results found on page {page}. Stopping pagination.")
                break

            if not results:
                log.info("No more results found.")
                break

            total_results += len(results)
            log.info(f"🎉 Found {total_results} reports for {topic}")

            for result in results:
                # Extract the URL
                url = result.get_attribute("href")
                title = result.find_element(By.TAG_NAME, "h3").text.strip()

                # Extract the publication date
                published_in_element = result.find_element(
                    By.XPATH,
                    ".//span[contains(text(),'Published in')]/following-sibling::span",
                )
                published_in = (
                    published_in_element.text.strip() if published_in_element else "N/A"
                )

                reports.append(
                    {"title": title, "url": url, "published_in": published_in}
                )

                print(f"Title: {title}")
                print(f"URL: {url}")
                print(f"Published in: {published_in}")
                print("-" * 50)

            page += 1
        report_count = len(reports)

        return reports, report_count

    except Exception as e:
        log.error(f"An error occurred while extracting report results: {e}")
        return reports, 0


def download_reports(driver, reports, topic):
    """
    Visit each report URL, download the corresponding file, and move it to the destination folder immediately.
    :param driver: Selenium WebDriver instance.
    :param reports: List of report dictionaries containing 'url' and 'title'.
    """
    global failed_reports

    if not os.path.exists(SOURCE_FOLDER):
        os.makedirs(SOURCE_FOLDER)

    for report in reports:
        try:
            url = report["url"]
            driver.get(url)

            # Wait for the download button to be present
            download_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "summaryBox__buttonDownload")
                )
            )

            # Trigger the download
            log.info(f"✅ Downloading report on page: {url}")
            download_button.click()

            # Wait for download to complete
            time.sleep(
                2
            )  # Adjust timeout as needed based on file size and download speed

            # Move and rename the file proactively
            move_latest_file_to_destination(report["title"], topic)
        except Exception as e:
            failed_reports += 1
            log.error(f"An error occurred while downloading from {url}: {e}")


def get_failed_reports_downloads():
    """Return the list of failed download URLs."""
    return failed_reports


def move_latest_file_to_destination(title, topic):
    """
    Move the latest downloaded file from the 'statista_data' folder to the destination folder
    and rename it based on the report title.
    :param title: The title of the report to use for renaming.
    :param topic: The topic to replace in the destination folder path.
    """
    try:
        # Sanitize the topic name to ensure consistency
        sanitized_topic = topic.lower().replace(" ", "-").strip()

        # Construct the destination folder path
        dest_folder = os.path.abspath(
            f"statista_data/{sanitized_topic}/advanced_reports"
        )

        # Ensure destination folder exists
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
            log.info(f"📂 Created folder: {dest_folder}")

        # Find the latest downloaded file in the source folder
        files = glob.glob(os.path.join(SOURCE_FOLDER, "*.xlsx"))
        if not files:
            log.warning(f"No files found in {SOURCE_FOLDER} to move.")
            return

        latest_file = max(files, key=os.path.getctime)
        file_name = os.path.basename(latest_file)

        # Generate a new name based on the report title
        sanitized_title = title.replace("/", "-").replace("\\", "-").strip()
        new_name = f"{sanitized_title} adv.xlsx"
        dest_path = os.path.join(dest_folder, new_name)

        # Move the file to the destination folder
        shutil.move(latest_file, dest_path)
        log.info(f"✅ Moved file to {dest_path}")
    except Exception as e:
        log.error(f"❌ Failed to move and rename file: {e}")


def open_xlsx_report_page(topic):
    """
    Navigate to the dynamically constructed XLSX report page and download the reports.
    Then move and rename the downloaded files.
    :param topic: The topic to search for in the reports. Defaults to None.
    """
    driver = setup_driver()
    try:
        log.info("Starting login process...")
        if not login_with_selenium(driver):
            log.error("Login failed. Exiting script.")
            return

        # Extract report results
        reports, _ = extract_report_results(driver, topic)
        log.info(f"Total reports found: {len(reports)}")

        # Download reports
        download_reports(driver, reports, topic)

    except Exception as e:
        log.error(f"An error occurred: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger()

    # Prompt the user for a topic (will be removed later, needs to be integrated into the gui)
    topic = input(
        "Enter a topic to search (or press Enter to load the default page): "
    ).strip()
    open_xlsx_report_page(topic if topic else None)

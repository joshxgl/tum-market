"""Browser test: notification panel opens below bell, above search."""
import sys

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import time


def run_case(driver, width, height, label):
    driver.set_window_size(width, height)
    driver.get("http://127.0.0.1:5000")
    time.sleep(1.2)
    driver.find_element(By.ID, "notificationBtn").click()
    time.sleep(0.6)

    panel = driver.find_element(By.ID, "notificationDropdown")
    assert "active" in (panel.get_attribute("class") or ""), f"{label}: panel not open"

    parent = driver.execute_script(
        "return document.getElementById('notificationDropdown').parentElement.tagName"
    )
    assert parent == "BODY", f"{label}: dropdown should be on body, got {parent}"

    btn = driver.find_element(By.ID, "notificationBtn")
    search = driver.find_element(By.CSS_SELECTOR, ".search-section")
    pb, bb, sb = panel.rect, btn.rect, search.rect

    panel_top = pb["y"]
    bell_bottom = bb["y"] + bb["height"]
    search_top = sb["y"]

    ok_below_bell = panel_top >= bell_bottom - 2
    ok_above_search = panel_top < search_top - 4

    print(f"[{label}] parent={parent} bell_bottom={bell_bottom:.0f} panel_top={panel_top:.0f} search_top={search_top:.0f}")
    print(f"  below bell: {ok_below_bell}, above search: {ok_above_search}")

    return ok_below_bell and ok_above_search


def main():
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Edge(options=options)
    try:
        ok = run_case(driver, 1280, 800, "desktop")
        ok &= run_case(driver, 390, 844, "mobile")
    finally:
        driver.quit()

    if ok:
        print("PASS: notification panel positioned correctly")
        return 0
    print("FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())

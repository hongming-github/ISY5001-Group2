from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium import webdriver

from bs4 import BeautifulSoup
import requests
import random
import json
import datetime
import os
import time
from urllib.parse import urljoin, urldefrag
import hashlib
from base import processor, utils
from time import sleep
import re
import pandas as pd
import urllib.parse
import pymysql
import numpy as np



#     course_number                 course number
#     title                         course name
#     classification                category name
#     second_classification         second-level category name
#     third_classification          third-level category name
#     language                      language
#     current_vacancy               current remaining vacancies
#     date_&_time                   time
#     registration_closing_date     course registration closing date
#     price                         price
#     course_description            course description
#     requirements                  course requirements
#     venue                         venue
#     organising_commitee           organizing committee
#     organising_commitee_url
#     training_provider(s)          trainer
#     training_provider(s)_url
COLS = ['course_number','title','classification','second_classification','third_classification','language','current_vacancy','date_&_time','registration_closing_date','price','course_description','requirements','venue','organising_commitee','organising_commitee_url','training_provider(s)','training_provider(s)_url','pageUrl','processStatus','imageurl']
EXCEL_PATH = 'data_sgcourse_health.xlsx'

if os.path.exists(EXCEL_PATH):
    df = pd.read_excel(EXCEL_PATH)
    for c in COLS:
        if c not in df.columns:
            df[c] = ''
    df = df[COLS]
else:
    df = pd.DataFrame(columns=COLS)

df.fillna('', inplace=True)

def urlnorm(base, href):
    if not href:
        return None
    u = urljoin(base, href)
    u, _ = urldefrag(u)
    return u

def pause():
    time.sleep(0.6 + random.random() * 0.7)

def wait_css(browser, css, timeout=20):
    try:
        WebDriverWait(browser, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
        return True
    except Exception:
        return False

def soup_from_browser(browser):
    return utils.get_content(browser.page_source)



SITE = {
    "domain": "https://www.onepa.gov.sg",
    "start": "https://www.onepa.gov.sg/courses",  # page 1

    # Hierarchical links
    "level1_links": "div.iconbox-tile-component div.button-tile-component_container.fixed-width-btn a",
    "level2_links": "div.textbox-tile-component a.button-tile-component_container_item_anchor",
    "level3_links": "div.textbox-tile-component a.button-tile-component_container_item_anchor",

    "list_item_links": "a.serp-grid__item",  # course card links

    # next button
    "list_next": "span.btnNext[role='link'][data-testid='btn-next']",

    "detail_course_number": "p.details-banner__code",
    "detail_title": "h3.details-banner__header",
    "detail_language": "h6.details-banner__language-text",
    "detail_vacancy": "div.details-banner__vacancy h6",
    "detail_datetime": "div.details-panel__datetime p.details-panel__text",
    "detail_reg_close": "div.details-panel__datetime p.details-panel__text--registration span",
    "detail_price": "p.details-panel__price-text",
    "detail_description": "p.details-description__text",
    "detail_requirements": "div.details-remarks p",
    "detail_venue": "p.details-venue__text",
    "detail_org_name": "div.organisercommitee-list a",
    "detail_org_url": "div.organisercommitee-list a",
    "detail_trainer_name": "div.details-organiser__right_name",
    "detail_trainer_btn": "div.details-organiser__right_profileLink",
    "detail_images": "div.details-banner__bg img",
}

class CollectionProcessor(processor.CrawlerProcessor):
    def __init__(self):
        super().__init__()
        self.browser = None

        self.v1 = set()
        self.v2 = set()
        self.v3 = set()
        self.vlist = set()
        self.vdetail = set()

    def _new_browser(self):
        opts = Options()
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,900")
        b = webdriver.Chrome(options=opts)
        b.set_page_load_timeout(40)
        return b

    def safe_get(self, url, retries=3):
        for i in range(retries):
            try:
                self.browser.get(url)
                return True
            except Exception as e:
                print(f"[WARN] Failed to open {url} {i + 1}/{retries}: {e}")
                time.sleep(5)
        return False

    def process(self, fetch_urls=True, fetch_details=True):
        global df
        try:
            if self.browser is None:
                self.browser = self._new_browser()

            if fetch_urls:
                home = SITE["start"]
                print(f"[HOME] {home}")
                self.browser.get(home)
                wait_css(self.browser, "body", 20)
                soup = soup_from_browser(self.browser)

                links = soup.select(SITE["level1_links"]) if SITE["level1_links"] else []
                for a in links:
                    href = a.get("href")
                    full_url = urlnorm(SITE["domain"], href)
                    name1 = a.get("title") or a.get_text(strip=True)
                    if name1.strip() != "Health & Wellness":
                        continue
                    if not full_url:
                        continue
                    pause()
                    self.crawl_level1(full_url, classification=name1)

            if fetch_details:
                self.fetch_all_details()

        finally:
            df.to_excel(EXCEL_PATH, index=False)
            print("********* Write successful *********")
            if self.browser:
                try:
                    self.browser.quit()
                except Exception:
                    pass

    def crawl_level1(self, url, classification=""):
        print(f"[L1] {url}")
        self.safe_get(url)
        wait_css(self.browser, "body", 20)
        soup = soup_from_browser(self.browser)

        links = soup.select(SITE["level2_links"]) if SITE["level2_links"] else []
        if not links:
            self.crawl_list_page(url, classification=classification)
            return

        for a in links:
            href = a.get("href")
            full_url = urlnorm(SITE["domain"], href)
            name2 = a.get("title") or a.get_text(strip=True)
            if not full_url or full_url in self.v1:
                continue
            self.v1.add(full_url)
            pause()
            self.crawl_level2(full_url, classification=classification, second_classification=name2)

    def crawl_level2(self, url2, classification="", second_classification=""):
        print(f"  [L2] {url2}")
        self.browser.get(url2)
        wait_css(self.browser, "body", 20)
        soup = soup_from_browser(self.browser)

        links = soup.select(SITE["level3_links"]) if SITE["level3_links"] else []
        if not links:
            self.crawl_list_page(url2, classification, second_classification)
            return

        for a in links:
            href = a.get("href")
            full_url = urlnorm(SITE["domain"], href)
            name3 = a.get("title") or a.get_text(strip=True)

            if not full_url or full_url in self.v2:
                continue
            self.v2.add(full_url)
            pause()
            self.crawl_level3(full_url, classification, second_classification, third_classification=name3)

    def crawl_level3(self, url3, classification="", second_classification="", third_classification=""):
        print(f"    [L3] {url3}")
        self.browser.get(url3)
        wait_css(self.browser, "body", 20)
        soup = soup_from_browser(self.browser)

        self.crawl_list_page(url3, classification, second_classification, third_classification)

    def crawl_list_page(self, list_url, classification="", second_classification="", third_classification=""):
        self.browser.get(list_url)
        wait_css(self.browser, "body", 20)

        while True:
            wait_css(self.browser, "a.serp-grid__item", 5)
            soup = soup_from_browser(self.browser)

            # Scrape current page course links
            items = [a.get("href") for a in soup.select(SITE["list_item_links"])]
            items = [urlnorm(list_url, h) for h in items if h]
            for detail in items:
                print(f"        [LIST] {detail}")
                self.enqueue_detail(detail, classification, second_classification, third_classification)

            from selenium.webdriver.support import expected_conditions as EC

            try:
                # Wait for "next page" button to appear and be clickable
                li_next = WebDriverWait(self.browser, 8).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "ul.pagination li span.btnNext"))
                )
                li_tag = li_next.find_element(By.XPATH, "..")  # parent li
                if "disabled" in li_tag.get_attribute("class").lower():
                    print("      [LIST] Already on the last page")
                    break

                curr_active = self.browser.find_element(
                    By.CSS_SELECTOR, "ul.pagination li.active span"
                ).get_attribute("id")

                self.browser.execute_script("arguments[0].click();", li_next)

                WebDriverWait(self.browser, 10).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, "ul.pagination li.active span").get_attribute(
                        "id") != curr_active
                )
                time.sleep(1.5)

            except Exception:
                print("      [LIST] no next page:")
                break

    def enqueue_detail(self, detail_url, classification="", second_classification="", third_classification=""):
        global df
        # if (df['pageUrl'] == detail_url).any():
        #     return
        new_row = {
            'course_number': '',
            'title': '',
            'classification': classification,
            'second_classification': second_classification,
            'third_classification': third_classification,
            'language': '',
            'current_vacancy': '',
            'date_&_time': '',
            'registration_closing_date': '',
            'price': '',
            'course_description': '',
            'requirements': '',
            'venue': '',
            'organising_commitee': '',
            'organising_commitee_url': '',
            'training_provider(s)': '',
            'training_provider(s)_url': '',
            'pageUrl': detail_url,
            'processStatus': 0,
            'imageurl': ''
        }
        df.loc[len(df)] = new_row
        if len(df) % 50 == 0:
            df.to_excel(EXCEL_PATH, index=False)
            print("      [LIST] saved 50 rows")

    def fetch_all_details(self):
        global df
        idx_list = df.index[df['processStatus'] == 0].tolist()
        for i in idx_list:
            ok = self.fetch_detail(df.at[i, 'pageUrl'], i)
            df.at[i, 'processStatus'] = 1 if ok else 2
            if i % 20 == 0:
                df.to_excel(EXCEL_PATH, index=False)
                print("  [DETAIL] saved 20 rows")
            pause()

    def fetch_detail(self, url, i):
        global df
        try:
            print(f"  [DETAIL] {url}")
            self.safe_get(url)
            wait_css(self.browser, "body", 25)
            soup = soup_from_browser(self.browser)

            el = soup.select_one(SITE["detail_course_number"])
            if el:
                text = el.get_text(strip=True)  # "Ref Code:  C027174293"
                code = text.replace("Ref Code:", "").strip()
                df.at[i, 'course_number'] = code

            el = soup.select_one(SITE["detail_title"])
            if el: df.at[i, 'title'] = el.get_text(strip=True)

            el = soup.select_one(SITE["detail_language"])
            if el: df.at[i, 'language'] = el.get_text(strip=True)

            el = soup.select_one(SITE["detail_vacancy"])
            if el: df.at[i, 'current_vacancy'] = el.get_text(strip=True)

            els = soup.select(SITE["detail_datetime"])
            if els:
                dt_texts = [e.get_text(" ", strip=True) for e in els]
                df.at[i, 'date_&_time'] = " | ".join(dt_texts)  # Join with |

            el = soup.select_one(SITE["detail_reg_close"])
            if el: df.at[i, 'registration_closing_date'] = el.get_text(strip=True)

            el = soup.select_one(SITE["detail_price"])
            if el: df.at[i, 'price'] = el.get_text(strip=True)

            el = soup.select_one(SITE["detail_description"])
            if el: df.at[i, 'course_description'] = el.get_text(" ", strip=True)

            el = soup.select_one(SITE["detail_requirements"])
            if el: df.at[i, 'requirements'] = el.get_text(" ", strip=True)

            el = soup.select_one(SITE["detail_venue"])
            if el: df.at[i, 'venue'] = el.get_text(" ", strip=True)

            a = soup.select_one(SITE["detail_org_name"])
            if a:
                df.at[i, 'organising_commitee'] = a.get_text(strip=True)
                href = a.get("href")
                if href:
                    from urllib.parse import urljoin
                    df.at[i, 'organising_commitee_url'] = urljoin(SITE["domain"], href)

            el = soup.select_one(SITE["detail_trainer_name"])
            if el:
                df.at[i, 'training_provider(s)'] = el.get_text(strip=True)

            try:
                btn = self.browser.find_element(By.CSS_SELECTOR, SITE["detail_trainer_btn"])
                self.browser.execute_script("arguments[0].click();", btn)
                time.sleep(3)

                trainer_url = self.browser.current_url
                df.at[i, 'training_provider(s)_url'] = trainer_url

                self.browser.back()
                time.sleep(3)

            except Exception:
                print("Trainer profile button not found")

            el = soup.select_one(SITE["detail_images"])
            if el:
                src = el.get("src")
                if src:
                    df.at[i, 'imageurl'] = urljoin(SITE["domain"], src)


            return True
        except Exception as e:
            print("  [DETAIL][ERR]", e)
            return False


if __name__ == '__main__':
    p = CollectionProcessor()
    p.process()

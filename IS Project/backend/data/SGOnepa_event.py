from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
import pickle

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



#     event_number                  活动编号
#     title                         活动名称
#     classification                分类名称
#     current_vacancy               目前剩余空余
#     date_&_time                   时间
#     registration_closing_date     活动注册截止日期
#     price                         价格
#     event_description             活动描述
#     venue                         地点
#     organising_commitee           举办委员会
#     organising_commitee_url
COLS = [ 'event_number', 'title', 'classification', 'current_vacancy', 'date_&_time',
         'registration_closing_date', 'price', 'event_description', 'venue', 'organising_commitee',
         'organising_commitee_url', 'pageUrl', 'processStatus']
EXCEL_PATH = 'data_sgevent.xlsx'

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

def save_cookies(browser, path="cookies.pkl"):
    with open(path, "wb") as f:
        pickle.dump(browser.get_cookies(), f)
    print("[INFO] cookies 已保存到", path)


def load_cookies(browser, path="cookies.pkl"):
    if not os.path.exists(path):
        print("[WARN] 没有找到 cookies.pkl，需要手动登录一次")
        return False

    with open(path, "rb") as f:
        cookies = pickle.load(f)

    for cookie in cookies:
        # 兼容 sameSite 错误值
        if "sameSite" in cookie and cookie["sameSite"] not in ["Strict", "Lax", "None"]:
            cookie["sameSite"] = "Lax"
        try:
            browser.add_cookie(cookie)
        except Exception as e:
            print("[WARN] 加载 cookie 出错:", e)

    print("[INFO] cookies 已加载")
    return True

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
    "start": "https://www.onepa.gov.sg/events",  # 网页1

    # 分级链接
    "level1_links": "div.icon-grid__item a.icon-grid__item-anchor",
    # "level2_links": "div.textbox-tile-component a.button-tile-component_container_item_anchor",
    # "level3_links": "div.textbox-tile-component a.button-tile-component_container_item_anchor",

    "list_item_links": "div.serp-grid a.serp-grid__item",

    #next按钮
    "list_next": "span.btnNext[role='link'][data-testid='btn-next']",

    "detail_vacancy": "div.details-banner__vacancy h6",
    "detail_reg_close": "div.details-panel__datetime p.details-panel__text-date",
    "detail_description": "div.richText",
    "detail_venue": "p.details-venue__text",
}

class CollectionProcessor:
    def __init__(self):
        self.browser = None
        self.first_detail = False

    def _new_browser(self):
        opts = Options()
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,900")
        b = webdriver.Chrome(options=opts)
        b.set_page_load_timeout(40)
        return b

    def login_with_cookies(self, home_url="https://www.onepa.gov.sg"):
        """尝试加载 cookies，如果没有就手动登录一次"""
        self.browser.get(home_url)

        # 如果有 cookies.pkl → 直接加载
        if load_cookies(self.browser):
            self.browser.refresh()
            print("[INFO] 已使用 cookies 登录")
            return

        # 否则需要手动登录一次
        print("[ACTION] 请在弹出的浏览器中手动完成登录，然后回到终端按回车继续...")
        input(">>> 等待手动登录完成后按回车继续：")

        # 登录后保存 cookies
        save_cookies(self.browser)

    def safe_get(self, url, retries=3):
        for i in range(retries):
            try:
                self.browser.get(url)
                return True
            except Exception as e:
                print(f"[WARN] 打开 {url} 失败 {i + 1}/{retries}: {e}")
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

                # 点击 Show More 按钮展开全部分类
                try:
                    show_more_btn = self.browser.find_element(By.CSS_SELECTOR,
                                                              "button[data-testid='showmoreless-toggle']")
                    self.browser.execute_script("arguments[0].click();", show_more_btn)
                    time.sleep(2)  # 等待页面刷新
                    print("[INFO] 已点击 Show More 展开分类")
                except Exception:
                    print("[INFO] 没有找到 Show More 按钮，可能已经展开")

                soup = soup_from_browser(self.browser)
                links = soup.select(SITE["level1_links"])
                for a in links:
                    href = a.get("href")
                    full_url = urlnorm(SITE["domain"], href)
                    name1 = a.get_text(strip=True)
                    if not full_url:
                        continue
                    pause()
                    self.crawl_list_page(full_url, classification=name1)

            if fetch_details:
                self.fetch_all_details()

        finally:
            df.to_excel(EXCEL_PATH, index=False)
            print("********* 写入成功 *********")
            if self.browser:
                try:
                    self.browser.quit()
                except Exception:
                    pass

    # def crawl_level1(self, url, classification=""):
    #     print(f"[L1] {url}")
    #     self.safe_get(url)
    #     wait_css(self.browser, "body", 20)
    #     soup = soup_from_browser(self.browser)
    #
    #     links = soup.select(SITE["level2_links"]) if SITE["level2_links"] else []
    #     if not links:
    #         self.crawl_list_page(url, classification=classification)
    #         return
    #
    #     for a in links:
    #         href = a.get("href")
    #         full_url = urlnorm(SITE["domain"], href)
    #         name2 = a.get("title") or a.get_text(strip=True)
    #         if not full_url or full_url in self.v1:
    #             continue
    #         self.v1.add(full_url)
    #         pause()
    #         self.crawl_level2(full_url, classification=classification, second_classification=name2)

    # def crawl_level2(self, url2, classification="", second_classification=""):
    #     print(f"  [L2] {url2}")
    #     self.browser.get(url2)
    #     wait_css(self.browser, "body", 20)
    #     soup = soup_from_browser(self.browser)
    #
    #     links = soup.select(SITE["level3_links"]) if SITE["level3_links"] else []
    #     if not links:
    #         self.crawl_list_page(url2, classification, second_classification)
    #         return
    #
    #     for a in links:
    #         href = a.get("href")
    #         full_url = urlnorm(SITE["domain"], href)
    #         name3 = a.get("title") or a.get_text(strip=True)
    #
    #         if not full_url or full_url in self.v2:
    #             continue
    #         self.v2.add(full_url)
    #         pause()
    #         self.crawl_level3(full_url, classification, second_classification, third_classification=name3)
    #
    # def crawl_level3(self, url3, classification="", second_classification="", third_classification=""):
    #     print(f"    [L3] {url3}")
    #     self.browser.get(url3)
    #     wait_css(self.browser, "body", 20)
    #     soup = soup_from_browser(self.browser)
    #
    #     self.crawl_list_page(url3, classification, second_classification, third_classification)

    def crawl_list_page(self, list_url, classification=""):
        self.browser.get(list_url)
        wait_css(self.browser, "body", 20)


        while True:
            soup = soup_from_browser(self.browser)
            cards = soup.select(SITE["list_item_links"])

            for a in cards:
                detail_url = urlnorm(list_url, a.get("href"))

                # event_number
                ref_span = a.select_one("div.serp-grid__item__left--course span")
                event_number = ""
                if ref_span and "Ref Code" in ref_span.text:
                    event_number = ref_span.text.replace("Ref Code:", "").strip()

                # title
                title_el = a.select_one("div.serp-grid__item__left__label")
                title = title_el.get_text(strip=True) if title_el else ""

                # organising committee + url
                org_el = a.select_one("div.serp-grid__item__left--course span.booking-declaration__yellow-link")
                org_name = org_el.get_text(strip=True) if org_el else ""
                if org_name.lower().startswith("by "):
                    org_name = org_name[3:].strip()
                org_url = ""
                cc_link = a.select_one("a.serp-grid__item__left__location")
                if cc_link:
                    org_url = urlnorm(SITE["domain"], cc_link.get("href"))

                # date & time
                date_el = a.select_one("span.serp-grid__item__left__date span")
                time_el = a.select_one("span.serp-grid__item__left__time span")
                date_time = ""
                if date_el:
                    date_time += date_el.get_text(strip=True)
                if time_el:
                    date_time += " " + time_el.get_text(strip=True)

                # price
                price_el = a.select_one("div.serp-grid__item__right__discount--member label")
                price = price_el.get_text(strip=True) if price_el else ""

                new_row = {
                    'event_number': event_number,
                    'title': title,
                    'classification': classification,
                    'current_vacancy': '',
                    'date_&_time': date_time,
                    'registration_closing_date': '',
                    'price': price,
                    'event_description': '',
                    'venue': '',
                    'organising_commitee': org_name,
                    'organising_commitee_url': org_url,
                    'pageUrl': detail_url,
                    'processStatus': 0
                }
                global df
                df.loc[len(df)] = new_row
                print(f"    [ITEM] {event_number} | {title}")

            # 翻页
            try:
                next_btn = WebDriverWait(self.browser, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, SITE["list_next"]))
                )
                self.browser.execute_script("arguments[0].click();", next_btn)
                time.sleep(2)
            except Exception:
                print("    [LIST] no next page")
                break

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
            if self.first_detail:
                print("[INFO] 第一次进入详情页，先暂停 60 秒")
                time.sleep(60)
                self.first_detail = False

            print(f"  [DETAIL] {url}")
            self.safe_get(url)
            wait_css(self.browser, "body", 25)
            soup = soup_from_browser(self.browser)

            el = soup.select_one(SITE["detail_vacancy"])
            if el: df.at[i, 'current_vacancy'] = el.get_text(strip=True)

            el = soup.select_one(SITE["detail_reg_close"])
            if el: df.at[i, 'registration_closing_date'] = el.get_text(strip=True)

            el = soup.select_one(SITE["detail_description"])
            if el:
                desc_text = el.get_text(" ", strip=True).replace("Event Description", "").strip()
                df.at[i, 'event_description'] = desc_text

            el = soup.select_one(SITE["detail_venue"])
            if el: df.at[i, 'venue'] = el.get_text(" ", strip=True)


            return True
        except Exception as e:
            print("  [DETAIL][ERR]", e)
            return False


if __name__ == '__main__':
    p = CollectionProcessor()
    p.browser = p._new_browser()   # 打开浏览器
    p.login_with_cookies("https://www.onepa.gov.sg")
    p.process()

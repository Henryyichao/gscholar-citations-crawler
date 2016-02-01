#!/usr/bin/env python

import logging
import math
import os.path
import sys
import time

import requests
from bs4 import BeautifulSoup

import myconfig

REQUEST_HEADERS = {"User-Agent": "Innocent Browser", "Accept-Charset": "UTF-8,*;q=0.5"}
SLEEP_INTERVAL = 60  # sleep in seconds before next request
CITATION_FILENAME = "citation.txt"

citation_num = 0
download_num = 0

session = requests.Session()

def get_start_citation_num():
    global CITATION_FILENAME
    if not os.path.exists(CITATION_FILENAME):
        return 0
    with open(CITATION_FILENAME, 'r') as f:
        citation_list = f.readlines()
        i = len(citation_list) - 1
        while i > -1:
            if citation_list[i][0] != '[':
                i -= 1
            else:
                break
        if i < 0:
            return 0
        last_line = citation_list[i]
        start_number = int(last_line[1:last_line.index(']')])
        logging.info('Start from citation [%d] ' % start_number)
        return start_number


def get_all_citations():
    global citation_num
    total_citations_num = get_total_citations_num()
    citation_num = get_start_citation_num()
    if citation_num > total_citations_num:
        logging.error(
            "Unexpected start citation number: %d, total citations number: %d" % (citation_num, total_citations_num))
        sys.exit(2)
    papers_per_page = 20
    paper_uri_template = myconfig.google_scholar_uri + "&cstart=%d&pagesize=%d"
    citation_num_bynow = 0
    continued = False
    page_num = 0
    while True:
        paper_uri = paper_uri_template % (papers_per_page * page_num, papers_per_page)
        logging.info("Processing GOOGLE_SCHOLAR_URI: " + paper_uri)
        soup = create_soup_by_url(paper_uri)
        paper_records = soup("tr", {"class": 'gsc_a_tr'})
        for p in paper_records:
            paper_title = p.find('a', {"class": "gsc_a_at"}).getText()
            logging.info("Processing paper: " + paper_title)
            citations_anchor = p.find('a', {"class": 'gsc_a_ac'})
            if citations_anchor['href']:
                citation_num_perpaper = int(citations_anchor.getText())
                citation_num_bynow += citation_num_perpaper
                if continued:
                    with open(CITATION_FILENAME, "a+") as f:
                        f.write("# %s\n" % paper_title.encode('utf-8'))
                    get_citations_by_paper(citations_anchor['href'], citation_num_perpaper, 0)
                elif citation_num_bynow > citation_num:
                    start_index_curr_paper = citation_num_perpaper - (citation_num_bynow - citation_num)
                    logging.debug('Continue from paper: %s, start index: %d' % (paper_title, start_index_curr_paper))
                    get_citations_by_paper(citations_anchor['href'], citation_num_perpaper, start_index_curr_paper)
                    continued = True
            else:
                logging.warn("Current paper has not been cited.")

        # has next page?
        next_button = soup.find('button', {"id": "gsc_bpf_next"})
        if "disabled" in dict(next_button.attrs):
            break
        else:
            page_num += 1


def get_total_citations_num():
    """
    Get the total citation number from user's google scholar homepage
    """
    soup = create_soup_by_url(myconfig.google_scholar_uri)
    total_citations_num = int(soup("td", {"class": "gsc_rsb_std"})[0].getText())
    logging.info("Total citations number: %d" % total_citations_num)
    return total_citations_num


def get_citations_by_paper(citations_uri, count, start_index):
    citations_uri_template = citations_uri + "&start=%d"
    for c in range(0, int(math.ceil((count - start_index) / 10.0))):
        curr_citations_uri = citations_uri_template % (c * 10 + start_index)
        logging.debug("Processing citations_uri: " + curr_citations_uri)
        soup = create_soup_by_url(curr_citations_uri)
        for citation_record in soup('div', {"class": "gs_r"}):
            save_citation(citation_record)


def save_citation(citation_record):
    CITE_DETAIL_URL_TEMPLATE = "https://scholar.google.com/scholar?q=info:%(id)s:scholar.google.com/&output=cite"
    cite_anchor = citation_record.find('a', {'class': 'gs_nph', 'href': '#', "role": "button"})
    if not cite_anchor:
        return
    citation_id = cite_anchor['onclick'].split(',')[1][1:-1]
    cite_detail_url = CITE_DETAIL_URL_TEMPLATE % {"id": citation_id}
    logging.info("Getting formated cite from " + cite_detail_url)
    soup = create_soup_by_url(cite_detail_url)
    global html_parser
    full_cite = soup.find("div", {"id": "gs_cit0"}).text
    global citation_num
    citation_num += 1
    with open(CITATION_FILENAME, "a+") as f:
        f.write("[%d] %s\n" % (citation_num, full_cite.encode('utf-8')))
    if myconfig.should_download:
        pdf_div = citation_record.find('div', {"class": "gs_ggs gs_fl"})
        if pdf_div:
            download_pdf(pdf_div.a['href'])


def download_pdf(pdf_url):
    global citation_num, download_num
    try:
        res = requests.get(pdf_url)
        with open("%d.pdf" % citation_num, "wb") as mypdf:
            mypdf.write(res.content)
        download_num += 1
        logging.info("Downloaded citation [%d] from link %s " % (citation_num, pdf_url))
    except Exception as err:
        logging.error("Can't download link: " + pdf_url + " Error: " + str(err))


def create_soup_by_url(page_url):
    global session
    try:
        time.sleep(SLEEP_INTERVAL)
        res = session.get(page_url, headers=REQUEST_HEADERS)
        soup = BeautifulSoup(res.content, "html.parser")
        if soup.h1 and soup.h1.text == "Please show you&#39;re not a robot":
            raise Exception("You need to verify manually that you're not a robot.")
        return soup
    except Exception as err:
        logging.error("Can't open link: " + page_url + " Error: " + str(err))
        sys.exit(1)


def main():
    logging.basicConfig(level=logging.DEBUG)
    get_all_citations()
    logging.info("Found %d citations and download %d files" % (citation_num, download_num))


if __name__ == "__main__":
    sys.exit(main())

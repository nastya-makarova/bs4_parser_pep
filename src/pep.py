import re
import requests_cache
from urllib.parse import urljoin
from bs4 import BeautifulSoup

PEP_DOC_URL = 'https://peps.python.org/'

session = requests_cache.CachedSession()
response = session.get(PEP_DOC_URL)
response.encoding = 'utf-8'
soup = BeautifulSoup(response.text, 'lxml')

tables = soup.find_all('tbody')

abbrs = []
for table in tables:
    abbrs.extend(table.find_all('abbr'))

main_abbrs = []
for abbr in abbrs:
    main_abbrs.append(abbr.text)

link_tags = []
for table in tables:
    link_tags.extend(table.find_all('a', {'class': 'pep reference internal'}))
links = link_tags[::2]

for link in links:
    pep_url = urljoin(PEP_DOC_URL, link['href'])
    response = session.get(pep_url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'lxml')
    table = soup.find('dl')
    status = table.find('dd', {'title': 'Currently valid informational guidance, or an in-use process'})
    print(status)




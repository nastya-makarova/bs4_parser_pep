import csv
import logging
import requests_cache
from urllib.parse import urljoin
from bs4 import BeautifulSoup


PEP_DOC_URL = 'https://peps.python.org/'

EXPECTED_STATUS = {
    'A': ('Active', 'Accepted'),
    'D': ('Deferred',),
    'F': ('Final',),
    'P': ('Provisional',),
    'R': ('Rejected',),
    'S': ('Superseded',),
    'W': ('Withdrawn',),
    '': ('Draft', 'Active'),
}

session = requests_cache.CachedSession()
response = session.get(PEP_DOC_URL)
response.encoding = 'utf-8'
soup = BeautifulSoup(response.text, 'lxml')

tables = soup.find_all('table', attrs={'class': 'pep-zero-table docutils align-default'})

table_bodies = []
statuses = []

for table in tables:
    table_bodies.extend(table.find_all('tbody'))


for body in table_bodies:
    rows = body.find_all('tr')
    for row in rows:
        status_tag = row.find('td')
        if len(status_tag.text) == 1:
            preview_status = ''
        preview_status = status_tag.text[1:]

        link_tag = status_tag.find_next_sibling()
        link = link_tag.find('a')

        pep_url = urljoin(PEP_DOC_URL, link['href'])
        response = session.get(pep_url)
        if response is None:
            continue
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'lxml')
        table = soup.find('dl')
        tags_dt = table.find_all('dt')

        for tag in tags_dt:
            main_status = None
            if tag.text == 'Status:':
                main_status = tag.find_next_sibling().text
                statuses.append(main_status)
                if main_status not in EXPECTED_STATUS[preview_status]:
                    info_msg = f'Несовпадающие статусы: {pep_url}'
                    f'Статус в карточке: {main_status}'
                    f'Ожидаемые статусы: {EXPECTED_STATUS[preview_status]}'
                    logging.info(info_msg, stack_info=True)
                break
        
data = [
    ['Статус', 'Количество'],
    ['Active', statuses.count('Active')],
    ['Accepted', statuses.count('Accepted')],
    ['Deferred', statuses.count('Active')],
    ['Final', statuses.count('Active')],
    ['Provisional', statuses.count('Active')],
    ['Rejected', statuses.count('Active')],
    ['Withdrawn', statuses.count('Active')],
    ['Draft', statuses.count('Active')],
    ['Active', statuses.count('Active')],
    ['Total', len(statuses)]
]
file_path = BASE_DIR / pep.csv
with open('pep.csv', mode='w') as file:
    writer = csv.writer(file)
    writer.writerows(data)
logging.info('Данные о статусах документов сохранены в файл pep.csv') 
import logging
import re
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from constants import (
    BASE_DIR,
    EXPECTED_STATUS,
    MAIN_DOC_URL,
    PEP_DOC_URL
)

from configs import configure_argument_parser, configure_logging
from outputs import control_output
from utils import get_response, get_results_dict, find_tag


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return

    soup = BeautifulSoup(response.text, features='lxml')

    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})

    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})

    sections_by_python = div_with_ul.find_all(
        'li',
        attrs={'class': 'toctree-l1'}
    )

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        response = get_response(session, version_link)
        soup = BeautifulSoup(response.text, features='lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append((h1.text, dl_text))

    return results


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Не найден список c версиями Python')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )

    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag,
        'a',
        {'href': re.compile(r'.+pdf-a4\.zip$')}
    )
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)

    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    results = get_results_dict(EXPECTED_STATUS)
    response = get_response(session, PEP_DOC_URL)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'lxml')
    # находим все подходящие таблицы
    tables = soup.find_all(
        'table',
        attrs={'class': 'pep-zero-table docutils align-default'}
    )
    table_bodies = []

    for table in tables:
        # необходимо только тело таблицы, без заголовка
        table_bodies.extend(table.find_all('tbody'))

    for body in table_bodies:
        # находим все строки
        rows = body.find_all('tr')
        for row in rows:
            status_tag = find_tag(row, 'td')
            # проверяем содержит ли тег статус
            preview_status = (
                status_tag.text[1:] if len(status_tag.text) > 1 else ''
            )
            if preview_status not in EXPECTED_STATUS:
                logging.info(f'Неожиданный статус: {preview_status}')
            # находим тег с ссылкой
            link_tag = status_tag.find_next_sibling()
            link = link_tag.find('a')
            pep_url = urljoin(PEP_DOC_URL, link['href'])

            response = get_response(session, pep_url)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'lxml')
            # находим первую таблицу
            table = soup.find('dl')
            # находим все теги dt
            tags_dt = table.find_all('dt')
            for tag in tags_dt:
                # определяем статус на странице PEP
                main_status = None
                # находим тег с текстом Status
                if tag.text == 'Status:':
                    # сам статус в следующем теге
                    main_status = tag.find_next_sibling().text
                    # проверяем совпадает ли статус на странице PEP
                    # со статусом в общем списке
                    if main_status not in EXPECTED_STATUS[preview_status]:
                        info_msg = (
                            f'Несовпадающие статусы: {pep_url}\n'
                            f'Статус в карточке: {main_status}\n'
                            'Ожидаемые статусы:'
                            f'{EXPECTED_STATUS[preview_status]}'
                        )
                        logging.info(info_msg)
                        continue
                    results[main_status] += 1
                    break
    results['Total'] = sum(results.values())
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')
    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)
    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()

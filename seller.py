import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """
    Получает список товаров магазина на Ozon.

    Аргументы:
        last_id (str): Последний обработанный ID товара.
        client_id (str): Идентификатор магазина на Ozon.
        seller_token (str): Токен доступа для авторизации в Ozon API.

    Возвращает:
        dict: Результат с данными о товарах (список товаров, общее количество и последний ID).

    Пример корректного исполнения:
        >>> get_product_list("", "123456", "abcdef")
        {"items": [...], "total": 100, "last_id": "xyz"}

    Пример некорректного исполнения:
        >>> get_product_list(123, "123456", "abcdef")  # Ошибка, last_id должен быть строкой.
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def get_offer_ids(client_id, seller_token):
    """
    Получить артикулы товаров магазина озон.

    Аргументы:
        client_id (str): Идентификатор магазина на Ozon.
        seller_token (str): Токен доступа для авторизации в Ozon API.

    Возвращает:
        list: Список артикулов товаров.

    Пример корректного исполнения:
        >>> get_offer_ids("123456", "abcdef")
        ["A123", "B456", "C789"]

    Пример некорректного исполнения:
        >>> get_offer_ids(123456, None)  # Ошибка, оба аргумента должны быть строками.
    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer_id"))
    return offer_ids


def update_price(prices: list, client_id, seller_token):
    """
    Обновить цены товаров.

    Аргументы:
        prices (list): Список с ценами товаров, где каждый элемент — это словарь с данными о цене.
        client_id (str): Идентификатор магазина на Ozon.
        seller_token (str): Токен доступа для авторизации в Ozon API.

    Возвращает:
        dict: Ответ от Ozon API о результате обновления.

    Пример корректного исполнения:
        >>> prices = [{"offer_id": "A123", "price": "1000"}]
        >>> update_price(prices, "123456", "abcdef")
        {"result": "success"}

    Пример некорректного исполнения:
        >>> update_price([], "123456", "abcdef")
        Ошибка, если список цен пустой, API Ozon не примет запрос.
    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks: list, client_id, seller_token):
    """
    Обновить остатки.

    Аргументы:
        stocks (list): Список остатков товаров, где каждый элемент — это словарь с данными об остатке.
        client_id (str): Идентификатор магазина на Ozon.
        seller_token (str): Токен доступа для авторизации в Ozon API.

    Возвращает:
        dict: Ответ от Ozon API о результате обновления.

    Пример корректного исполнения:
        >>> stocks = [{"offer_id": "A123", "stock": 10}]
        >>> update_stocks(stocks, "123456", "abcdef")
        {"result": "success"}

    Пример некорректного исполнения:
        >>> update_stocks([], "123456", "abcdef")
        Ошибка, если список остатков пустой, API Ozon не примет запрос.
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def download_stock():
    """
    Скачать файл ostatki с сайта casio.

    Аргументы:
        Отсутствуют.

    Возвращает:
        list: Список товаров с остатками (каждый товар представлен как словарь с атрибутами).

    Пример корректного исполнения:
        >>> download_stock()
        [{"Код": "A123", "Количество": ">10", "Цена": "5990.00 руб."}]

    Пример некорректного исполнения:
        Нет аргументов для ошибки, но может быть ошибка подключения к сайту поставщика.
    """
    # Скачать остатки с сайта
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    # Создаем список остатков часов:
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    os.remove("./ostatki.xls")  # Удалить файл
    return watch_remnants


def create_stocks(watch_remnants, offer_ids):
    """
    Формирует список остатков для отправки в Ozon.

    Аргументы:
        watch_remnants (list): Список товаров с остатками от поставщика.
        offer_ids (list): Список артикулов товаров в магазине Ozon.

    Возвращает:
        list: Список остатков в формате для Ozon.

    Пример корректного исполнения:
        >>> remnants = [{"Код": "A123", "Количество": ">10"}]
        >>> ids = ["A123", "B456"]
        >>> create_stocks(remnants, ids)
        [{"offer_id": "A123", "stock": 100}, {"offer_id": "B456", "stock": 0}]

    Пример некорректного исполнения:
        >>> create_stocks({}, ["A123"])  # Ошибка, watch_remnants должен быть списком.
    """
    # Уберем то, что не загружено в seller
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    return stocks


def create_prices(watch_remnants, offer_ids):
    """
    Формирует список цен для отправки в Ozon.

    Аргументы:
        watch_remnants (list): Список товаров с остатками от поставщика.
        offer_ids (list): Список артикулов товаров в магазине Ozon.

    Возвращает:
        list: Список цен в формате для Ozon.

    Пример корректного исполнения:
        >>> remnants = [{"Код": "A123", "Цена": "5990.00 руб."}]
        >>> ids = ["A123"]
        >>> create_prices(remnants, ids)
        [{"offer_id": "A123", "price": "5990"}]

    Пример некорректного исполнения:
        >>> create_prices("A123", ["A123"])  # Ошибка, watch_remnants должен быть списком.
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    return prices


def price_conversion(price: str) -> str:
    """
    Преобразует строку с ценой в числовой формат, удаляя лишние символы.

    Аргументы:
        price (str): Цена в виде строки, например, "5'990.00 руб.".

    Возвращает:
        str: Преобразованная строка с числовым значением цены, например, "5990".

    Пример корректного исполнения:
        >>> price_conversion("5'990.00 руб.")
        '5990'

    Пример некорректного исполнения:
        >>> price_conversion(5990)  # Ошибка, price должен быть строкой.
    """

    return re.sub("[^0-9]", "", price.split(".")[0])



def divide(lst: list, n: int):
    """
    Разделить список lst на части по n элементов.

    Аргументы:
        lst (list): Список, который нужно разделить.
        n (int): Количество элементов в каждой части.

    Возвращает:
        generator: Генератор, который возвращает части списка, каждая длиной n.

    Пример корректного исполнения:
        >>> list(divide([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]

    Пример некорректного исполнения:
        >>> list(divide([1, 2], "2"))  # Ошибка, n должен быть числом.
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def upload_prices(watch_remnants, client_id, seller_token):
    """
    Загружает обновленные цены товаров в Ozon.

    Аргументы:
        watch_remnants (list): Список товаров с остатками и ценами от поставщика.
        client_id (str): Идентификатор магазина на Ozon.
        seller_token (str): Токен доступа для авторизации в Ozon API.

    Возвращает:
        list: Список цен, которые были загружены в Ozon.

    Пример корректного исполнения:
        >>> watch_remnants = [{"Код": "A123", "Цена": "5990.00 руб."}]
        >>> upload_prices(watch_remnants, "123456", "abcdef")
        [{"offer_id": "A123", "price": "5990"}]

    Пример некорректного исполнения:
        >>> upload_prices({}, "123456", "abcdef")  # Ошибка, watch_remnants должен быть списком.
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices


async def upload_stocks(watch_remnants, client_id, seller_token):
    """
    Загружает обновленные остатки товаров в Ozon.

    Аргументы:
        watch_remnants (list): Список товаров с остатками от поставщика.
        client_id (str): Идентификатор магазина на Ozon.
        seller_token (str): Токен доступа для авторизации в Ozon API.

    Возвращает:
        tuple: Кортеж, содержащий два списка — товары с ненулевыми остатками и полный список остатков.

    Пример корректного исполнения:
        >>> watch_remnants = [{"Код": "A123", "Количество": ">10"}]
        >>> upload_stocks(watch_remnants, "123456", "abcdef")
        ([{"offer_id": "A123", "stock": 100}], [{"offer_id": "A123", "stock": 100}])

    Пример некорректного исполнения:
        >>> upload_stocks({}, "123456", "abcdef")  # Ошибка, watch_remnants должен быть списком.
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks


def main():
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        # Обновить остатки
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        # Поменять цены
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()

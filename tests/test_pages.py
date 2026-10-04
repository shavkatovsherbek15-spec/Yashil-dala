import pytest

from app.web import safe_next


@pytest.mark.parametrize(
    "url",
    ["/", "/katalog", "/katalog?cat=himoya&crop=olma&sort=price_asc", "/mahsulot/npk-20-20-20", "/savatcha"],
)
def test_pages_ok(client, url):
    assert client.get(url).status_code == 200


def test_404(client):
    r = client.get("/mahsulot/yoq")
    assert r.status_code == 404
    assert "Sahifa topilmadi" in r.text


def test_catalog_filters(client):
    r = client.get("/katalog?cat=uy")
    assert "1 ta mahsulot" in r.text
    assert "Tarakanga qarshi gel" in r.text

    # Ekin filtri: olma uchun ro'yxatdan o'tganlar
    r = client.get("/katalog?crop=olma")
    assert "Tarakanga qarshi gel" not in r.text
    assert "Kanaga qarshi akaritsid" in r.text

    # Muammo nomi bo'yicha qidiruv
    r = client.get("/katalog?q=fitoftoroz")
    assert "1 ta mahsulot" in r.text
    assert "fungitsid" in r.text


def test_product_usage_table(client):
    r = client.get("/mahsulot/shiraga-qarshi-insektitsid")
    assert "Ruxsat etilgan ekinlar va doza" in r.text
    assert "Shira, Trips" in r.text
    assert "Kartoshka" not in r.text


def test_lang_switch(client):
    r = client.get("/til/ru?next=/katalog", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/katalog"
    assert "lang=ru" in r.headers["set-cookie"]


@pytest.mark.parametrize("url", ["https://evil.uz", "//evil.uz", "/\\evil.uz", "katalog"])
def test_safe_next_blocks_external(url):
    assert safe_next(url) == "/"

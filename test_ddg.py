from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        response = page.goto(
            "https://duckduckgo.com/?q=bactador+anti+odeur+avis&ia=web",
            timeout=20000,
            wait_until="domcontentloaded"
        )
        page.wait_for_timeout(2500)

        print("STATUT HTTP :", response.status if response else "inconnu")
        print("TITRE PAGE :", page.title())
        print("URL FINALE :", page.url)

        titles = page.locator(
            'article h2, [data-testid="result-title-a"]'
        ).all_inner_texts()

        print("TITRES DDG :")
        for title in titles[:6]:
            print("-", title)

    except Exception as exc:
        print("ERREUR :", exc)
        print("URL :", page.url)
    finally:
        browser.close()

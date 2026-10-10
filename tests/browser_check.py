"""Optional browser smoke check; run with server on port 8011 and Playwright installed."""
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8011", wait_until="networkidle")
    assert "Catálogo" in page.title()
    page.locator("#search").fill("jose de acosta")
    page.get_by_role("button", name="José de Acosta Ver ficha", exact=True).click()
    page.locator(".metadata").wait_for()
    frame = page.frame_locator("iframe")
    frame.locator("canvas").wait_for()
    page.locator(".publications li a").first.click()
    page.get_by_text("Ficha bibliográfica · BIBFRAME", exact=True).wait_for()
    assert page.locator(".publications .metadata").count() > 0
    page.screenshot(path="data/catalogo-publicacion.png", full_page=True)
    page.go_back()
    page.locator("iframe").wait_for()
    page.locator("iframe").scroll_into_view_if_needed()
    page.frame_locator("iframe").locator("canvas").wait_for()
    page.screenshot(path="data/catalogo-actor.png", full_page=True)
    page.goto("http://127.0.0.1:8011/grafo", wait_until="load", timeout=60000)
    page.locator("canvas").wait_for(timeout=60000)
    counts = page.evaluate("({nodes:nodes.length, edges:edges.length})")
    assert counts["edges"] > 70000
    page.get_by_role("button", name="Pausar", exact=True).click()
    page.screenshot(path="data/catalogo-grafo.png")
    print({"graph": counts, "browser_errors": errors}, flush=True)
    assert not errors
    browser.close()

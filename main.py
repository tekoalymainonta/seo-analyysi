from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup, Tag
from urllib.parse import urlparse, urlunparse
import json
import re

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<title>Sivuston crawlaus</title>
<h1>Analysoi sivusto</h1>
<form method="post">
  <input name="url" style="width:400px" placeholder="Syötä URL esim. https://esimerkki.fi">
  <input type="submit" value="Crawlaa">
</form>
<pre>{{ result }}</pre>
"""

def normalize_url(url):
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        return urlunparse(("https", netloc, path, "", "", ""))
    except:
        return url

def is_footer_tag(tag):
    if tag.name == "footer":
        return True
    if tag.has_attr("id") and "footer" in tag["id"].lower():
        return True
    if tag.has_attr("class") and any("footer" in cls.lower() for cls in tag["class"]):
        return True
    return False

def get_navigation(soup):
    nav_links = []
    nav = soup.find("nav")
    if nav:
        for a in nav.find_all("a"):
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if text:
                nav_links.append(f"{text} ({href})")
    return nav_links

def extract_ordered_content(soup):
    body = soup.body
    if not body:
        return []

    elements = []
    seen_texts = set()

    def extract_texts(tag):
        if not isinstance(tag, Tag):
            return
        if tag.name in ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "strong", "em", "span"]:
            text = tag.get_text(strip=True)
            if text and text not in seen_texts:
                elements.append({"tag": tag.name, "text": text})
                seen_texts.add(text)
        for child in tag.children:
            extract_texts(child)

    # Käy läpi kaikki osat bodyssä, mutta vältä nav/footer
    for section in body.find_all(recursive=False):
        if is_footer_tag(section) or section.name == "nav":
            continue
        extract_texts(section)

    return elements[:20]  # rajoitetaan silti 20 osaan, jos tarpeen

def extract_internal_and_external_links(soup):
    links = []
    for tag in soup.body.find_all("a", href=True):
        if is_footer_tag(tag) or any(p.name == "nav" for p in tag.parents):
            continue
        text, href = tag.get_text(strip=True), tag["href"]
        if text and href:
            links.append({"text": text, "href": href})
    return links

def extract_images(soup):
    images = []
    for img in soup.body.find_all("img"):
        if is_footer_tag(img) or any(p.name == "nav" for p in img.parents):
            continue
        src = img.get("src", "").strip()
        alt = img.get("alt", "").strip()
        if src:
            images.append({"src": src, "alt": alt})
    return images

def extract_json_ld(soup):
    json_ld_data = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = script.string
            if content:
                parsed = json.loads(content.strip())
                json_ld_data.append(parsed)
        except json.JSONDecodeError:
            continue
    return json_ld_data

def get_page_data(url, html=None):
    try:
        url = normalize_url(url)
        if html is None:
            r = requests.get(url, timeout=10)
            html = r.text
        soup = BeautifulSoup(html, "html.parser")

        meta_title = soup.title.string if soup.title else ""
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta_desc_tag.get("content") if meta_desc_tag else ""

        navigation = get_navigation(soup)
        ordered_content = extract_ordered_content(soup)
        content_links = extract_internal_and_external_links(soup)
        images = extract_images(soup)
        json_ld = extract_json_ld(soup)

        return {
            "url": url,
            "meta_title": meta_title,
            "meta_description": meta_desc,
            "navigation_links": navigation,
            "ordered_content": ordered_content[:10],
            "content_links": content_links[:10],
            "images": images[:5],
            "json_ld": json_ld
        }
    except Exception as e:
        return {"url": url, "error": str(e)}

def crawl_site(root_url, max_pages=30, max_depth=2):
    visited = set()
    queue = [(normalize_url(root_url), 0)]
    results = []

    while queue and len(results) < max_pages:
        url, depth = queue.pop(0)
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        try:
            r = requests.get(url, timeout=10)
            html = r.text
            page_data = get_page_data(url, html)
            results.append(page_data)

            if depth < max_depth:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if href.startswith("#") or "?" in href:
                        continue
                    full = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                    norm = normalize_url(full)
                    if norm not in visited:
                        queue.append((norm, depth + 1))
        except:
            continue

    return results

@app.route("/", methods=["GET", "POST"])
def index():
    result = ""
    if request.method == "POST":
        url = request.form.get("url")
        if url:
            pages = crawl_site(url)
            result = f"=== Crawlaustulos ({len(pages)} sivua) ===\n\n"
            result += json.dumps(pages, indent=2, ensure_ascii=False)
        else:
            result = "URL puuttuu!"
    return render_template_string(TEMPLATE, result=result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)

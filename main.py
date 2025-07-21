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
import openai
import os

# Aseta OpenAI-API-avain ympäristömuuttujista
from openai import OpenAI
client = OpenAI()

ANALYSIS_PROMPT = """
Toimi SEO- ja tekoälyasiantuntijana ja tee analyysi crawlauksen antaman datan pohjalta. Arvioi jokaisen crawlatun sivun elementit sivukohtaisesti seuraavasti: 
1. Tekninen toteutus perus seo:n ja tekoälyn näkökulmasta (tarkemmat ohjeet myöhemmin kunkin elementin kohdalla).
- Meta tietojen toteutus
- Avainsanojen määrä ja toistuvuus
- Tekstin pituus 
- Otsikoiden käyttö
- kuvien alt tekstit
- Strukturoidun datan (scheman) käyttö
- Sisäiset ja ulkoiset linkit
2. Arvioi myös, että tukevatko elementit kokonaisuutena sivua ja sen sisältöä seo:n ja tekoälyn näkökulmasta. 

Vastauksen muoto: 
- Rivi 1: sivun nimi
- Rivi 2: elementin otsikko (esim metaotsikot ja kuvaukset)
- Rivi 3: kommentti/arvio.

Vastauksen sisältö: 
- Jos analyysin perusteella elementti on hyvin toteutettu, niin anna vastauksesi vain teksti: HYVÄ
- Jos elementin toteutuksessa on puutteita, huomautettavaa, ristiriitaisuuksia tai virheitä, niin anna vastaukseksi kuvaus kyseisestä asiasta.
- Älä anna suosituksia

HUOM! Älä tee navigaatiosta arviota jokaisella sivulla. Lisää navigaatio elementin arvio loppuun omalle riville ennen verkkosivutson kokonaisarviota.

Arvioi myös verkkosivustoa kokonaisuutena:
1. Ota huomioon, että onko kysessä paikallinen yritys, palvelualue yritys, verkkokauppa tai liidejä keräävä ei pelkästään paikallinen toimija. 
2. Tukeeko sivuston sivut toisiaan. 
3. Esiintyvätkö palveluihin ja tuotteisiin sekä mahdolliseen paikallisuuteen viittaavat avainsanat kokonaisuuden kannalta niin, että ne tukevat sitä, mutta ei aiheuta avainsana kannibalismia tai "Keyword stuffingia". 
4. Tukeeko sisältö avainsanojen lisäksi myös asiayhteyttä/kontekstia. 
5. Onko sivustolla selkeä ja looginen hierarkia. 
6. Onko sivut linkitetty toisiinsa niin, että käyttäjän on helppo edetä sivulla syvällisempään tietoon tai kohti osto, ajanvaraus, yhteydenottoa tai muuta liiketoiminann kannalta tavoiteltavaa toimintoa. 

Vastauksen muoto: 
- Vapaa muotoinen analyysin loppuun

Vastauksen sisältö: 
- Yhteenveto, jossa tuotu esiin, mitkä sivut ja niiden elementit ovat kokonaisuuden kannalta hyvin toteutettu ja mitkä eivät. 
- Älä anna suosituksia.

Alla on lueteltu elementit ja tarkennut, että mitä niissä tulee arvioida

1. Metaotsikot ja -kuvaukset
Ovatko ne informatiivisia suhteessa kunkin sivun sisältöön?
Vastaavatko ne sivun aiheeseen, ja tukevatko sivuston kokonaisuutta?
Onko niissä avainsanoja luonnollisesti ja tasapainoisesti?
Ohjaavatko ne lukijaa toimintaan ja herättävätkö kiinnostuksen?

2. Navigaatio
Onko navigaatiorakenne selkeä ja looginen koko sivuston tasolla?
Löytyykö navigaatio kaikilta sivuilta yhtenäisesti?
Tukeeko navigaatio sisällön rakenteellista ymmärtämistä ja käyttäjän kulkua?

3. Pääsisältö (ordered_content)
Vastaako sisältö kunkin sivun otsikkoa ja tukee sivuston kokonaisuutta?
Onko jäsentely hyvä: otsikot, väliotsikot, leipäteksti ja bulletit?
Onko sisältö riittävän laajaa mutta ei tarpeettomasti toistelevaa?
Millainen on kirjoitustyyli? Onko se yhtenäinen ja sopiva kohderyhmälle?
Mikä on sisällön SEO-potentiaali:
Avainsanojen näkökulmasta (perinteinen hakukone)
Kontekstuaalisesta näkökulmasta (tekoälyn tarjoamat vastaukset)?

4. Taggaamaton sisältö
Älä arvioi itse sisältöä.
Jos taggaamatonta sisältöä esiintyy paljon, huomauta tästä: analyysi ei huomioi niitä, ja se voi vaikuttaa tuloksiin.
Suosittele korjaamaan sisältö rakenteelliseksi (esim. p, h2, h3, li) tulevia arviointeja varten.

5. Linkitys
Ovatko ankkuritekstit kuvaavia ja lukukokemusta tukevia?
Miten sisäinen linkitys toimii rakenteena? Ohjaako se käyttäjää loogisesti?
Tukeeko linkitys päätavoitteita (esim. osto, tiedonhaku)?
Jos ulkoisia linkkejä on, vievätkö ne luotettaviin ja tarkoituksenmukaisiin kohteisiin?

6. Kuvat
Onko kuvia riittävästi ja eri sivuilla?
Toistuvatko samat kuvat vai tukevatko ne yksilöllisesti sivun sisältöä?
Onko alt-tekstit käytössä? Ovatko ne informatiivisia ja SEO:ta tukevia?

7. Sivun yläosa (Hero / Intro content)
Löytyykö selkeä H1-otsikko, ja kuvaako se sivun sisältöä kattavasti?
Onko mukana alaotsikko tai tekstikappale, joka selittää tarkemmin sivun aiheen?
Sisältääkö hero-osio call to action -elementtejä (esim. painikkeita, linkkejä)?
Tukeeko hero-osio käyttäjän päätöksentekoa ja ohjaa toimintaa tehokkaasti?
"""

def analyze_site_data(pages):
    try:
        with open("seo_knowledge.txt", "r", encoding="utf-8") as f:
            seo_knowledge = f.read()
        print("== SEO Knowledge loaded successfully ==")
    except Exception as e:
        print(f"Error reading seo_knowledge.txt: {e}")
        seo_knowledge = ""

    print("== SEO Knowledge Preview ==")
    print(seo_knowledge[:500])

    if not seo_knowledge.strip():
        print("Warning: seo_knowledge.txt is empty or missing content!")

    simplified = []
    for p in pages:
        simplified.append({
            "url": p["url"],
            "meta_title": p.get("meta_title",""),
            "meta_description": p.get("meta_description",""),
            "navigation_links": p.get("navigation_links", []),
            "ordered_content": [ {"tag": el["tag"], "text": el["text"]} 
                                 for el in p.get("ordered_content", [])[:10] ],
            "content_links": p.get("content_links", [])[:10],
            "images": p.get("images", [])[:5]
        })

    user_msg = json.dumps(simplified, ensure_ascii=False)
    if len(user_msg) > 20000:
        user_msg = user_msg[:20000]

    system_msg = f"""
{seo_knowledge}

{ANALYSIS_PROMPT.strip()}
""".strip()

    from openai import OpenAI

    client = OpenAI()

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        max_tokens=2000,
        temperature=0.2,
    )

    return resp.choices[0].message.content

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

def get_schema_data(soup):
    schemas = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = json.loads(script.string)
            schemas.append(content)
        except:
            continue
    return schemas

def get_navigation(soup):
    nav_links = []
    nav = soup.find("nav")
    if nav:
        for a in nav.find_all("a"):
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if text:
                nav_links.append(f"{text} ({href})")
    else:
        body = soup.body
        if not body:
            return nav_links
        for tag in body.find_all():
            if tag.name == "h1":
                break
            if tag.name == "a":
                text = tag.get_text(strip=True)
                href = tag.get("href", "")
                if text:
                    nav_links.append(f"{text} ({href})")
    return nav_links

def extract_ordered_content(soup):
    body = soup.body
    if not body:
        return []

    elements, start = [], False
    for element in body.descendants:
        if isinstance(element, Tag):
            if is_footer_tag(element):
                break
            if element.name == "h1":
                start = True
            if start and element.name in ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]:
                text = element.get_text(strip=True)
                if text:
                    elements.append({"tag": element.name, "text": text})

    cleaned, i = [], 0
    while i < len(elements):
        curr = elements[i]
        if curr["tag"] == "li" and i + 2 < len(elements):
            next1, next2 = elements[i + 1], elements[i + 2]
            if next1["tag"].startswith("h") and next2["tag"] == "li":
                heading, bodytext = next1["text"].strip(), next2["text"].strip()
                full = curr["text"].strip()
                if full.startswith(heading) and full[len(heading):].strip() == bodytext:
                    cleaned += [next1, next2]
                    i += 3
                    continue
        cleaned.append(curr)
        i += 1

    return cleaned

def extract_untagged_text_blocks(soup, already_collected_texts):
    untagged, seen_texts = set(), set()
    allowed_tags = {"p", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "nav", "footer", "section", "strong", "em", "b", "i", "span"}
    skip_tags = {"script", "style", "nav", "footer"}

    for element in soup.body.find_all(string=True):
        parent = element.parent
        if not parent or parent.name in skip_tags:
            continue
        if any(p.name in allowed_tags for p in element.parents):
            continue
        text = element.strip()
        if len(text) < 40:
            continue
        normalized = re.sub(r"\s+", " ", text)
        if normalized not in seen_texts and normalized not in already_collected_texts:
            seen_texts.add(normalized)
            untagged.add(normalized)

    return list(untagged)

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

        schema = get_schema_data(soup)
        navigation = get_navigation(soup)
        ordered_content = extract_ordered_content(soup)
        word_count = sum(len(re.findall(r'\b\w+\b', item["text"])) for item in ordered_content)
        collected_texts = {re.sub(r"\s+", " ", item["text"].strip()) for item in ordered_content}
        untagged_blocks = extract_untagged_text_blocks(soup, collected_texts)
        content_links = extract_internal_and_external_links(soup)
        images = extract_images(soup)

        return {
            "url": url,
            "meta_title": meta_title,
            "meta_description": meta_desc,
            "schema": schema,
            "navigation_links": navigation,
            "text_word_count": word_count,
            "ordered_content": ordered_content,
            "untagged_text_blocks": untagged_blocks,
            "content_links": content_links,
            "images": images
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
            analysis = analyze_site_data(pages)
            result = f"=== Crawlaustulos ({len(pages)} sivua) ===\n\n"
            result += "=== Analyysi ===\n"
            result += analysis
        else:
            result = "URL puuttuu!"
    return render_template_string(TEMPLATE, result=result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
# render_lib.py
import base64
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

KIT = Path(__file__).parent
FONTDIR = Path('/home/claude/node_modules/@fontsource/inter/files')

SYMS = {"ZAR":"R","USD":"$","EUR":"\u20ac","GBP":"\u00a3"}

STANDARD_TERMS = {
 "standard_za_international":[
  "This is a quotation only. No reservations have been made and all services are subject to availability at the time of booking.",
  "Prices are calculated on discounted airfares with limited availability; the actual fare is confirmed at the time of booking, dependent on the airline and class available.",
  "Fares and airport taxes are subject to change without prior notice due to currency fluctuations or airfare increases, until full payment has been made and documentation issued.",
  "Prices are based on the rate of exchange on the day of quotation and remain subject to change until full payment is received.",
  "Passports must be valid for at least 6 months after your intended return to South Africa, with at least 3 blank pages.",
  "Children under 18 must travel with an unabridged birth certificate together with a valid passport.",
  "Please ensure that traveller names and surnames match your ID / passport exactly; failure to do so could cause inconvenience or denied boarding.",
  "Professional fees apply to all transactions and are not refundable in the case of cancellation.",
  "We will never notify you of a change to our bank details by email. If you receive such an email, do not act on it and contact us immediately.",
  "E&OE: errors and omissions excepted.",
 ],
}

def money(amount, sym):
    return f"{sym} {amount:,.2f}".replace(",", " ")

def price_option(pricing):
    sym = SYMS.get(pricing.get("currency","ZAR"), pricing.get("currency","R"))
    grand = 0.0; taxes_total = 0.0
    for line in pricing.get("lines", []):
        n = line.get("count",1)
        sub = (line["fare_pp"] + line.get("taxes_pp",0.0)) * n
        taxes_total += line.get("taxes_pp",0.0)*n
        grand += sub
        line.setdefault("pax_label", f"{line.get('pax_type','Item')} \u00d7 {n}")
        line["fare_fmt"] = money(line["fare_pp"], sym)
        line["taxes_fmt"] = money(line.get("taxes_pp",0.0), sym)
        line["subtotal_fmt"] = money(sub, sym)
    pricing["taxes_total_fmt"] = money(taxes_total, sym)
    pricing["vat_fmt"] = money(pricing.get("vat",0.0), sym)
    pricing["grand_total_fmt"] = money(grand, sym)
    return sym

def font_block():
    faces=[]
    for w in (400,500,600,700,800):
        for style in ("normal","italic"):
            f=FONTDIR/f"inter-latin-{w}-{style}.woff2"
            if f.exists():
                faces.append(f"@font-face{{font-family:'Inter';font-style:{style};font-weight:{w};src:url('file://{f}') format('woff2');}}")
    return "<style>\n"+"\n".join(faces)+"\n</style>" if faces else \
        '<link href="https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400..800;1,400..800&display=swap" rel="stylesheet">'

def render_html_from_quote(quote_obj):
    q = quote_obj.copy()
    for f in ("reference","date","valid_until","consultant","client","trip"):
        if f not in q:
            raise ValueError(f"Missing mandatory field: {f}")
    if not (q.get("flight_options") or q.get("accommodation")):
        raise ValueError("Need at least flights or accommodation")

    for fo in q.get("flight_options", []):
        sym = price_option(fo["pricing"])
        for grp in fo.get("groups", []):
            if "fare" in grp:
                grp["fare_fmt"] = money(grp["fare"], sym)

    for dest in q.get("accommodation", []):
        for h in dest.get("options", []):
            sym = SYMS.get(h.get("currency","ZAR"),"R")
            h["price_fmt"] = money(h.get("price",0.0), sym)

    for t in q.get("transfers", []) or []:
        if "rate" in t: t["rate_fmt"] = money(t["rate"], SYMS.get(t.get("currency","ZAR"),"R"))
    for r in q.get("rail", []) or []:
        if "rate" in r: r["rate_fmt"] = money(r["rate"], SYMS.get(r.get("currency","ZAR"),"R"))

    q["terms"] = STANDARD_TERMS.get(q.get("terms_profile","standard_za_international"), []) + q.get("custom_notes", [])
    logo_b64 = base64.b64encode((Path(__file__).parent/"logo.png").read_bytes()).decode()

    env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=False)
    html = env.get_template("template.html").render(q=q, logo_b64=logo_b64, font_block=font_block())
    return html

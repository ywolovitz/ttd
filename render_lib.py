# render_lib.py
import base64
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

KIT = Path(__file__).parent
FONTDIR = KIT / "fonts"

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

# Flat fees (same currency as the item) that are added to the item's total.
# JSON key -> formatted key written back onto the item.
FEE_FIELDS = {
    "markup": "markup_fmt",
    "transaction_fee": "transaction_fee_fmt",
    "cancellation_fee": "cancellation_fee_fmt",
    "change_fee": "change_fee_fmt",
}

def num(value, default=0.0):
    """ Returns value as a number; None, empty or non-numeric text gives default."""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).strip().replace(" ", ""))
    except ValueError:
        return default

def sym_for(currency, default="ZAR"):
    """ Currency symbol; unknown currencies show their code (e.g. AUD) instead of R."""
    cur = currency or default
    return SYMS.get(cur, cur)

def money(amount, sym):
    """ Returns SYM xxx xxx.xx"""
    return f"{sym} {num(amount):,.2f}".replace(",", " ")

def apply_fees(item, base, sym):
    """
    Adds markup, transaction_fee, cancellation_fee and change_fee (flat amounts, None/missing = 0)
    to base. Mutates item by adding markup_fmt, transaction_fee_fmt, cancellation_fee_fmt,
    change_fee_fmt, fees_total_fmt, subtotal_before_fees_fmt and total_fmt.

    Args:
    item: the dict holding the fee fields (accommodation option, car rental, experience, pricing)
    base: the amount before fees
    sym: currency symbol

    Returns the total (base + fees) as a float.
    """
    fees_total = 0.0
    for key, fmt_key in FEE_FIELDS.items():
        amt = num(item.get(key))
        fees_total += amt
        item[fmt_key] = money(amt, sym)
    total = base + fees_total
    item["subtotal_before_fees_fmt"] = money(base, sym)
    item["fees_total_fmt"] = money(fees_total, sym)
    item["total_fmt"] = money(total, sym)
    return total

def price_option(pricing):
    """
    Takes the pricing part of flight options, calculates grand total, fares, taxes, fees and subtotal.
    It mutates pricing by adding fare_fmt, taxes_fmt and subtotal_fmt onto each line and adding
    taxes_total_fmt, vat_fmt, markup_fmt, transaction_fee_fmt, cancellation_fee_fmt, change_fee_fmt,
    fees_total_fmt, subtotal_before_fees_fmt and grand_total_fmt onto pricing.

    grand total = sum of line subtotals + markup + transaction fee + cancellation fee + change fee.
    Fees are flat amounts per flight option; None or missing counts as 0.

    Args:

    pricing: flight pricing json

    returns the currency symbol of pricing.
    """
    sym = sym_for(pricing.get("currency"))
    grand = 0.0; taxes_total = 0.0
    for line in pricing.get("lines", []):
        n = num(line.get("count",1), 1)
        if n <= 0: # Count Invalid , count can only be 1 and up.
            n = 1
        n = int(n)
        fare_pp = num(line.get("fare_pp"))
        taxes_pp = num(line.get("taxes_pp"))
        sub = (fare_pp + taxes_pp) * n
        taxes_total += taxes_pp * n
        grand += sub
        line.setdefault("pax_label", f"{line.get('pax_type','Item')} \u00d7 {n}")
        line["fare_fmt"] = money(fare_pp, sym)
        line["taxes_fmt"] = money(taxes_pp, sym)
        line["subtotal_fmt"] = money(sub, sym)

    grand = apply_fees(pricing, grand, sym)
    pricing["taxes_total_fmt"] = money(taxes_total, sym)
    pricing["vat_fmt"] = money(num(pricing.get("vat")), sym)
    pricing["grand_total_fmt"] = pricing["total_fmt"]
    return sym

def font_block():
    """
    Returns an HTML string for the document <head>: a <style> block of @font-face
    rules built from whichever local .woff2 files exist under FONTDIR, or a Google
    Fonts <link> tag if none exist at all.
 
    Checks each of the 10 weight/style combinations individually, but the fallback
    itself is all-or-nothing: if at least one local file is found, only those local
    @font-face rules are emitted (any missing weight/style is simply absent, with no
    per-missing-file fallback to Google Fonts); the Google Fonts link is only used
    when zero local font files are found."""
    faces=[]
    for w in (400,500,600,700,800):
        for style in ("normal","italic"):
            f=FONTDIR/f"inter-latin-{w}-{style}.woff2"
            if f.exists():
                faces.append(f"@font-face{{font-family:'Inter';font-style:{style};font-weight:{w};src:url('file://{f}') format('woff2');}}")
    return "<style>\n"+"\n".join(faces)+"\n</style>" if faces else \
        '<link href="https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400..800;1,400..800&display=swap" rel="stylesheet">'

def render_html_from_quote(quote_obj):
    """
    Takes a quote JSON Object checks presence of critical points, formats numbers and money amounts, then passes this on to HTML to process with Jinja.

    Flights, accommodation options, car rentals and experiences (excursions) each get their
    markup / transaction / cancellation / change fees added to their total.

    Args:
    quote_obj: Quote JSON Object

    Returns:
    
    HTML: Quote HTML

    Raises:

    ValueError: if reference, date, valid until, consultant, client or trip is not in the JSON.
    
    """
    q = quote_obj.copy()
    for f in ("reference","date","valid_until","consultant","client","trip"):
        if f not in q:
            raise ValueError(f"Missing mandatory field: {f}")

    for fo in q.get("flight_options", []):
        sym = price_option(fo["pricing"])
        for grp in fo.get("groups", []):
            if "fare" in grp:
                grp["fare_fmt"] = money(num(grp.get("fare")), sym)

    for dest in q.get("accommodation", []):
        for h in dest.get("options", []):
            sym = sym_for(h.get("currency"))
            base = num(h.get("price"))
            apply_fees(h, base, sym)
            h["price_fmt"] = h["total_fmt"]  # PDF shows the all-in total only

    for t in q.get("transfers", []) or []:
        if "rate" in t:
            sym = sym_for(t.get("currency"))
            apply_fees(t, num(t.get("rate")), sym)
            t["rate_fmt"] = t["total_fmt"]  # PDF shows the all-in total only
    for r in q.get("rail", []) or []:
        if "rate" in r:
            sym = sym_for(r.get("currency"))
            apply_fees(r, num(r.get("rate")), sym)
            r["rate_fmt"] = r["total_fmt"]  # PDF shows the all-in total only

    for c in q.get("car_rentals", []) or []:
        sym = sym_for(c.get("currency"))
        base = num(c.get("price"))
        apply_fees(c, base, sym)
        c["price_fmt"] = c["total_fmt"]  # PDF shows the all-in total only

    for e in q.get("experiences", []) or []:
        sym = sym_for(e.get("currency"))
        base = num(e.get("price"))
        apply_fees(e, base, sym)
        e["price_fmt"] = e["total_fmt"]  # PDF shows the all-in total only

    for stop in q.get("itinerary_overview", []) or []:
        stop["nights"] = num(stop.get("nights"), 0)

    q["terms"] = STANDARD_TERMS.get(q.get("terms_profile","standard_za_international"), []) + (q.get("custom_notes") or [])
    logo_b64 = base64.b64encode((Path(__file__).parent/"logo.png").read_bytes()).decode()

    env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=False)
    html = env.get_template("template.html").render(q=q, logo_b64=logo_b64, font_block=font_block())
    return html

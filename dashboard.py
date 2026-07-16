"""Genereert een interactief HTML-dashboard van de tenders-database."""

import sqlite3
from datetime import datetime
from collections import defaultdict

DB = "tenders.db"


def stats():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    totaal = c.execute("SELECT count(*) FROM tenders").fetchone()[0]
    per_bron = c.execute("SELECT bron, count(*) FROM tenders GROUP BY bron").fetchall()
    per_status = c.execute("SELECT status, count(*) FROM tenders GROUP BY status").fetchall()
    meest_recent = c.execute(
        "SELECT eerst_gezien FROM tenders ORDER BY eerst_gezien DESC LIMIT 1"
    ).fetchone()[0]

    rijen = c.execute("SELECT * FROM tenders ORDER BY publicatiedatum DESC").fetchall()
    conn.close()

    return {
        "totaal": totaal,
        "per_bron": per_bron,
        "per_status": per_status,
        "meest_recent": meest_recent,
        "rijen": rijen,
    }


def html_table(rijen):
    rows = []
    for r in rijen[:100]:  # Eerste 100
        rows.append(f"""
        <tr>
            <td>{r[0]}</td>
            <td>{r[2]}</td>
            <td><strong>{r[3]}</strong></td>
            <td>{r[4]}</td>
            <td>{r[5]}</td>
            <td>{r[7][:10] if r[7] else '-'}</td>
            <td><a href="{r[8]}" target="_blank">link</a></td>
        </tr>
        """)
    return "\n".join(rows)


def main():
    s = stats()

    bron_html = "\n".join(
        f"<li><strong>{b}</strong>: {c} tenders</li>" for b, c in s["per_bron"]
    )
    status_html = "\n".join(
        f"<li><strong>{st}</strong>: {c}</li>" for st, c in s["per_status"]
    )

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tender Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; margin-bottom: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card h2 {{ font-size: 14px; color: #666; margin-bottom: 10px; text-transform: uppercase; }}
        .card .number {{ font-size: 32px; font-weight: bold; color: #0066cc; }}
        .card ul {{ margin-top: 15px; padding-left: 20px; }}
        .card li {{ margin: 8px 0; color: #555; }}
        table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; margin-top: 20px; }}
        th {{ background: #0066cc; color: white; padding: 12px; text-align: left; font-weight: 600; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f9f9f9; }}
        a {{ color: #0066cc; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #999; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Tender Dashboard</h1>
        <p style="color: #666; margin-bottom: 20px;">Bijgewerkt: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</p>

        <div class="stats">
            <div class="card">
                <h2>Totaal</h2>
                <div class="number">{s['totaal']}</div>
            </div>
            <div class="card">
                <h2>Per bron</h2>
                <ul>{bron_html}</ul>
            </div>
            <div class="card">
                <h2>Per status</h2>
                <ul>{status_html}</ul>
            </div>
        </div>

        <h2 style="margin-top: 30px; color: #333;">Recente tenders (eerste 100)</h2>
        <table>
            <tr>
                <th>Bron</th>
                <th>Nummer</th>
                <th>Titel</th>
                <th>Organisatie</th>
                <th>Status</th>
                <th>Deadline</th>
                <th>Link</th>
            </tr>
            {html_table(s["rijen"])}
        </table>

        <div class="footer">
            <p>Automatisch gegenereerd door tender-scraper</p>
        </div>
    </div>
</body>
</html>"""

    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("dashboard.html geschreven")


if __name__ == "__main__":
    main()

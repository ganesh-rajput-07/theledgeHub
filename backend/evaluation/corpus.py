"""A small fictional company knowledge base. Facts are deliberately spread across pages and documents,
with look-alike distractors (our revenue vs a competitor's, leave vs remote work) so retrieval has to
discriminate rather than just match keywords."""

from pathlib import Path

import pymupdf

CORPUS: dict[str, list[str]] = {
    "northwind-annual-report-2025.pdf": [
        """Northwind Analytics - Annual Report 2025

Letter from the CEO. 2025 was the year Northwind Analytics became a profitable company. We closed the
year with 1,240 customers across 31 countries, up from 905 customers a year earlier. Our CEO, Meera Iyer,
founded the company in Pune in 2016 together with CTO Daniel Okafor.

Northwind builds forecasting software for retail and logistics businesses. Our flagship product, Northwind
Forecast, predicts demand at store and warehouse level so customers can plan stock and staffing.""",
        """Financial overview

Total revenue for fiscal year 2025 was INR 412 crore, an increase of 38 percent over the INR 298 crore
reported for fiscal year 2024. Recurring subscription revenue made up 81 percent of the total.

Operating profit reached INR 37 crore, compared with an operating loss of INR 22 crore in fiscal year 2024.
Gross margin improved from 68 percent to 74 percent, mainly because cloud hosting costs per customer fell.

The fiscal year runs from 1 April to 31 March.""",
        """Outlook and risks

For fiscal year 2026 the board approved a target of INR 540 crore in revenue. The largest planned
investment is a new data centre region in Singapore, budgeted at INR 60 crore, to serve customers in
Southeast Asia with lower latency and local data residency.

The main risks we see are pricing pressure from larger competitors, dependence on two cloud vendors,
and hiring enough senior machine learning engineers.""",
    ],
    "competitor-analysis-q4.pdf": [
        """Competitor analysis - Q4 2025

Our closest competitor is Stratus Retail AI, headquartered in Bengaluru. Stratus reported revenue of
INR 655 crore for fiscal year 2025, growing 21 percent year on year. Stratus is larger than Northwind but
grew more slowly.

Stratus sells mainly to grocery chains and charges per store per month, while Northwind charges per
forecasted product line.""",
        """Second competitor: Helio Demand, a Singapore company, focuses on logistics. Helio raised a USD 45 million
Series C in October 2025 and is expanding into India.

Win/loss: in Q4 2025 Northwind won 62 percent of competitive deals against Stratus and 48 percent against
Helio. The most common reason for losing deals was the lack of a native SAP integration.""",
    ],
    "hr-leave-policy.pdf": [
        """Leave policy (effective 1 January 2025)

Every full-time employee is entitled to 24 days of paid annual leave per calendar year. Up to 8 unused
days can be carried over to the next year; the rest lapse on 31 December.

Employees also receive 12 days of paid sick leave per year. A doctor's certificate is required for sick
leave longer than 3 consecutive days.""",
        """Parental leave. Birthing parents receive 26 weeks of fully paid maternity leave. Non-birthing parents
receive 6 weeks of fully paid paternity leave, which must be taken within 12 months of the birth or adoption.

Leave requests are submitted in the PeopleHub portal and must be approved by the employee's manager at
least two weeks in advance, except for sick leave and emergencies.""",
    ],
    "remote-work-policy.pdf": [
        """Remote and hybrid work policy

Employees may work remotely up to 3 days per week. Teams agree on two common office days so that people
meet in person regularly. Fully remote arrangements need approval from a vice president.

Northwind pays a one-time home office allowance of INR 40,000 for a desk, chair and monitor, plus
INR 2,000 per month towards internet costs.""",
        """Working from abroad is allowed for up to 30 days per calendar year, provided the employee informs
the People team at least two weeks before travelling. Longer stays abroad are not permitted because of
tax and payroll rules.

Remote employees must use the company VPN on any network that is not the office network.""",
    ],
    "information-security-policy.pdf": [
        """Information security policy

All employees must enable multi-factor authentication on their Northwind account, using an authenticator
app or a hardware key. SMS codes are not accepted.

Passwords must be at least 14 characters long. Passwords are not rotated on a schedule; they are changed
only when there is reason to believe they were exposed.""",
        """Security incidents, including lost laptops and suspected phishing, must be reported to
security@northwind.example within 1 hour of discovery.

Customer data is encrypted at rest with AES-256 and in transit with TLS 1.3. Production database backups
are taken every 6 hours and retained for 35 days. Laptops are encrypted with full-disk encryption and are
wiped remotely if lost.""",
    ],
    "forecast-product-manual.pdf": [
        """Northwind Forecast - product manual (version 4.2)

Northwind Forecast produces a 13-week demand forecast for every product and location, refreshed every
night at 02:00 local time. Forecasts include an 80 percent prediction interval so planners can see the
uncertainty.

Data is imported from CSV files, Shopify, or the REST API. Each import may contain at most 5 million rows.""",
        """REST API

The public REST API allows 600 requests per minute per API key. Requests above the limit receive HTTP 429
with a Retry-After header. API keys are created by workspace administrators in Settings > Developers.

The API is versioned in the URL; the current version is v3. Version v2 will be switched off on
30 June 2026.""",
        """Accuracy and support

On the 2025 benchmark of 120 retail customers, Northwind Forecast achieved a mean absolute percentage
error (MAPE) of 11.8 percent at the weekly level.

Support is available 24/7 for Enterprise plans with a 1 hour response target for critical issues. Standard
plans have business-hours support with a 1 business day response target.""",
    ],
}


def build_pdfs(directory: Path) -> dict[str, Path]:
    """Writes each document as a real PDF (one page per entry) and returns filename -> path."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for filename, pages in CORPUS.items():
        doc = pymupdf.open()
        for text in pages:
            page = doc.new_page()
            overflow = page.insert_textbox(pymupdf.Rect(56, 56, 540, 790), text, fontsize=11)
            if overflow < 0:
                raise ValueError(f"{filename}: page text does not fit on one PDF page")
        path = directory / filename
        doc.save(path)
        doc.close()
        paths[filename] = path
    return paths

Analyze this research report excerpt and extract the following metadata:

1. **Bank/Source**: The investment bank or institution that published this report (e.g., Goldman Sachs, JPMorgan, UBS, Morgan Stanley, Barclays, Citi, Deutsche Bank, HSBC, BNP Paribas, Societe Generale).
   Return the common abbreviation: GS, JPM, UBS, MS, BARC, CITI, DB, HSBC, BNP, SG

2. **Asset Class**: The primary asset class discussed. Choose from:
   - equity (stocks, sectors)
   - fixed_income (bonds, credit)
   - multi_asset (cross-asset, macro strategy)
   - fx (currencies)
   - rates (interest rates)
   - credit (corporate bonds, HY, IG)
   - commodities

3. **Report Date**: The publication date of this report in YYYY-MM-DD format.

4. **Title**: The report title if visible.

Respond ONLY with valid JSON in this exact format:
{{ "bank": "XX", "asset_class": "xxx", "report_date": "YYYY-MM-DD", "title": "Report Title" }}

If you cannot determine a field, use "UNKNOWN" for strings.

---
DOCUMENT EXCERPT:
{excerpt}

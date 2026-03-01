# CRA RSU Tax Ledger (Subsection 7(1.31) Logic)

This application is a specialized tax-tracking tool designed for Canadian employees who receive **Restricted Stock Units (RSUs)**. It automates the complex "identical properties" math required by the **Canada Revenue Agency (CRA)**, specifically focusing on the **30-day "Holding Tank"** rules and the **Weighted Average Adjusted Cost Base (ACB) Pool**.

---

## 🔗 Official Government Resources
To verify these rules or provide documentation to your accountant, refer to the following official links:

* **[Income Tax Act - Section 7(1.31)](https://laws-lois.justice.gc.ca/eng/acts/I-3.3/section-7.html):** The legislation regarding the "30-day" designation for securities acquired under employee agreements.
* **[CRA: Completing Schedule 3 (Capital Gains)](https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/completing-schedule-3.html):** General instructions on how to report stock sales.
* **[CRA: Identical Properties & Average Cost](https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/special-rules-other-transactions.html#Identical_properties):** Guidance on why you must average the cost of shares and the specific exceptions (like the 30-day rule).

---

## ✨ Core Features
* **Automated FX Fetching:** Connects to the **Bank of Canada Valet API** for official USD/CAD noon rates.
* **Weekend Lookback:** Automatically pulls the rate for the nearest preceding business day if a vest occurs on a weekend (CRA compliant).
* **Subsection 7(1.31) Isolation:** Tracks shares in a "30-day isolation tank" before merging them into the general pool. This ensures that "sell-to-cover" events (Auto-Sales) result in near-zero capital gains.
* **Weighted Average ACB:** Once shares exceed the 30-day window, they "graduate" into a long-term pool where the cost basis is averaged in both USD and CAD.
* **Audit Trail:** Generates "Audit Notes" explaining exactly which shares were used for each sale (Tank vs. Pool).



---

## 🧮 How the Math Works

### 1. The 30-Day Holding Tank
When an RSU **Vests**, the shares enter a temporary "Tank." 
* Per **Subsection 7(1.31)**, if you **Sell** shares within 30 days of that vest, you can designate those specific shares as the ones sold. 
* This prevents your high-priced new shares from being "diluted" by old, low-cost shares in your main pool.

### 2. The ACB Pool
If shares remain in your account for **more than 30 days**, they graduate. The system recalculates your **Weighted Average Cost**:

$$\text{New Average CAD} = \frac{(\text{Total Pool Cost CAD}) + (\text{New Vest Cost CAD})}{\text{Total Shares in Pool}}$$

### 3. Currency Conversion
The CRA requires capital gains to be reported in **CAD**. The ledger uses the Bank of Canada's daily exchange rate. If a rate is missing (weekend/holiday), the tool performs a 5-day lookback for the most recent valid rate.

---

## 🚀 User Guide

1.  **Add Entry:** Click **"+ Add Event"** for every Vest and Sale event on your brokerage statement.
2.  **Input Data:**
    * **Date:** The date the shares landed in your account.
    * **Type:** * `VEST`: New shares arriving.
        * `AUTO-SALE`: Shares sold immediately to cover taxes.
        * `SALE`: A personal sale of shares you’ve been holding.
    * **USD Price & Shares:** Enter exactly what appears on your statement.
3.  **Calculate:** Click **"Calculate & Sync."**
    * The system will fetch FX rates and populate the "Proceeds" and "Cost Basis" columns.

---

## 📝 Tax Filing (Schedule 3)
When filing your taxes, use the totals from this ledger for your **Schedule 3**:
* **Proceeds of Disposition:** Total from the "Proceeds (CAD)" column.
* **Adjusted Cost Base:** Total from the "Cost Basis (ACB)" column.



---

## 🛠️ Technical Setup
1.  Ensure **Python 3.x** and **Flask** are installed:
    ```bash
    pip install flask requests
    ```
2.  Run the application:
    ```bash
    python app.py
    ```
3.  Navigate to `http://127.0.0.1:5000` in your browser.
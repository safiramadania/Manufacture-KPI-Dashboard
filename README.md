# Manufacture KPI Dashboard (Downtime & Performance)

This project builds an end-to-end workflow to **clean manufacturing batch data**, compute **downtime KPIs**, and deliver a **Streamlit overview dashboard** to monitor performance and identify the biggest downtime drivers (Pareto / 80-20).

---

## Dashboard Preview
<img width="1919" height="964" alt="image" src="https://github.com/user-attachments/assets/10f06ad2-b2d2-4604-96e7-627efb06d90f" />

**What you can do in the dashboard:**
- Filter data by **date range**, **product**, and **operator** (sidebar)
- Monitor core KPIs:
  - **Total Downtime (min)**
  - **Average Downtime Rate**
  - **Average Run Ratio**
  - **Total Batches**
- Explore trends:
  - **Daily Total Downtime** (line chart)
  - **Daily Average Downtime Rate** (line chart)
- Understand root causes:
  - **Top Downtime Reasons** + **Pareto (cumulative %)**
- Investigate outliers:
  - **Worst Batches table** (highest downtime)

---

## Dataset

- `line-productivity.csv` — batch logs (Date, Product, Batch, Operator, Start Time, End Time)
- `line-downtime.csv` — downtime minutes by factor per batch (wide format)
- `products.csv` — product metadata + minimum batch time
- `downtime-factors.csv` — factor descriptions + operator error flag
- `metadata.csv` — field descriptions

---

## Data Engineering Process (Notebook)

All data processing steps are implemented in: `Data_Engineering.ipynb`.

### 1) Load & Standardize
- Read raw CSV files using `sep="|"`
- Standardize column names with `.str.strip()` to avoid hidden whitespace issues

### 2) Data Quality Checks
- Detect and quantify:
  - Non-data header row in `line-downtime.csv` (`Batch == "Batch"`)
  - Non-numeric batch IDs
  - Datetime parsing failures in productivity logs
  - Cross-midnight cases (`end_dt < start_dt`)
  - Uniqueness issues in dimension tables (`products`, `factors`)

### 3) Cleaning
**Productivity (`line-productivity.csv`)**
- Drop rows missing essential fields (Date/Product/Batch/Operator/Start/End)
- Parse datetime: `start_dt`, `end_dt`
- Fix cross-midnight batches by adding `+1 day` to `end_dt`
- Compute `duration_min`

**Downtime (`line-downtime.csv`)**
- Remove the non-data header row
- Convert `Batch` to integer
- Convert factor columns to numeric and fill missing with `0`

**Products (`products.csv`)**
- Convert `Min batch time` to numeric
- Drop invalid values and ensure `Product` keys are unique

**Downtime Factors (`downtime-factors.csv`)**
- Convert `Factor` to integer and ensure uniqueness
- Detect and normalize the operator-error column name 

### 4) Transformations
- **Transform downtime wide → long** using `melt()`:
  - From: one row per batch with many factor columns
  - To: one row per `(Batch, Factor)` with `downtime_min`
- Extract numeric factor IDs (e.g., `"Factor 1"` → `1`)
- **Join downtime with factor descriptions** to map factor IDs into human-readable reasons

### 5) Build Fact Table 
Create a batch-level dataset for analytics/dashboard:

- Aggregate downtime per batch: `downtime_total_min`
- Join with productivity logs and product metadata
- Compute KPI columns:
  - `actual_run_min = duration_min - downtime_total_min`
  - `downtime_rate = downtime_total_min / duration_min`
  - `run_ratio = actual_run_min / duration_min`

---

## Outputs

Generated files (created by the notebook):
- `data_processed/fact_batches.parquet`
- `data_processed/fact_downtime_long.parquet`

These are used by the Streamlit dashboard (`app.py`).

---

## Project Structure
```
.
├─ app.py
├─ Data_Engineering.ipynb
├─ requirements.txt
├─ data_raw/
├─ data_processed/          # generated outputs
└─ docs/
   └─ dashboard_overview.png
```

---

## How to Run Locally

### 1) Create & activate virtual environment
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Generate processed data
Run `Data_Engineering.ipynb` until the **Save outputs** section to generate:
- `data_processed/fact_batches.parquet`
- `data_processed/fact_downtime_long.parquet`

### 4) Run the dashboard
```bash
streamlit run app.py
```

Open the local URL shown in the terminal (usually `http://localhost:8501`).

---

## KPI Definitions (Quick Reference)
- **Batch Duration (min)**: `duration_min = end_dt - start_dt`
- **Total Downtime (min)**: sum downtime minutes across factors per batch
- **Actual Run Time (min)**: `actual_run_min = duration_min - downtime_total_min`
- **Downtime Rate**: `downtime_rate = downtime_total_min / duration_min`
- **Run Ratio**: `run_ratio = actual_run_min / duration_min`

---

## Author
Safira Madania

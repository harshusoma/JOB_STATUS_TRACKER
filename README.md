# 🚀 Job Status Tracker — Automated ATS Job Status Updater

### Built by **Harsha Soma (harshusoma)**

Track 2000+ job applications automatically — across Workday, Greenhouse, LinkedIn, and more.

---

## 📌 Overview

**Job Status Tracker** is an end-to-end automation system that:

- Reads job applications from a **Google Sheets** workbook
- Visits each job URL (Workday, Greenhouse, Lever, LinkedIn, etc.)
- Detects job status (Open, Closed, Expired, Rejected, Under Review)
- Updates your Google Sheet automatically
- Caches Workday passwords per tenant
- Provides a full **interactive dashboard** using Streamlit
- Supports daily automated scanning (GitHub Actions)

This system replaces **manual job tracking** and gives you **real-time updates** across 2000+ job applications.

---

## 🧠 Features

### ✔ Google Sheets Integration

Your sheet stays updated LIVE — no need for Excel files.

### ✔ Status Detection

Automatically detects:

- Job Closed
- Job Expired
- Position Filled
- No Longer Accepting Applications
- Workday "Under Review", "In Process"
- LinkedIn "Viewed", "Submitted", "Rejected"

### ✔ ATS Support

Supports major ATS job portals:

- Workday
- Greenhouse
- Lever
- SmartRecruiters
- Taleo
- Generic career pages

### ✔ Workday Smart Login

- Multi-password fallback
- Tenant-level caching
- Auto-detection of the correct login credentials
- Zero manual intervention

### ✔ LinkedIn Optional Login

Can skip LinkedIn login to avoid CAPTCHA.

### ✔ Dashboard

A powerful Streamlit dashboard:

- Application counts
- Status distribution
- Platform breakdown
- Multi-sheet data
- Full filtering & analysis

### ✔ Daily Automation

Optional GitHub Actions workflow to auto-scan daily at 7AM.

---

## 🛠 Tech Stack

- **Python 3.11+**
- **Playwright** (job page automation)
- **Google Sheets API**
- **gspread**
- **Streamlit** (dashboard)
- **OAuth2 Service Account**
- **dotenv**
- **GitHub Actions**

---

## 📁 Project Structure

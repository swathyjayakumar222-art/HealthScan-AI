# HealthScan-AI 🩺

An AI-powered health dashboard designed to help users track vital signs, monitor health trends, and analyze medical reports in one place.

## 📌 About the Project

HealthScan-AI is a web application that provides a personal health dashboard. Users can record vital readings, view health information, upload medical reports, and access report analysis through a frontend connected to a Flask backend.

## ✨ Features

- **Health Dashboard:** View an overview of recorded health information.
- **Vitals Tracking:** Add and store health readings.
- **Vitals Trends:** Visualize changes in health readings over time.
- **Medical Report Upload:** Upload medical reports for processing.
- **Report Extraction and Analysis:** Extract information from supported reports and display analysis.
- **Recent Readings:** Review previously recorded vital measurements.
- **Frontend–Backend Integration:** Communicate with a Flask API.

## 🛠️ Technologies Used

**Frontend**
- React
- Vite
- JavaScript
- HTML
- CSS

**Backend**
- Python
- Flask
- REST API

**Database and Storage**
- MySQL, if configured in your project
- Uploaded reports and health readings, depending on your backend implementation

## 📸 Screenshots

### 1. Dashboard

![HealthScan-AI Dashboard](frontend/screenshots/dashboard.png)

### 2. Vitals Trends

![Vitals Trends](frontend/screenshots/vitals-trends.png)

### 3. Add Vitals

![Add Vitals](frontend/screenshots/add-vitals.png)

### 4. Medical Report Analysis

![Medical Report Analysis](frontend/screenshots/medical-report.png)

## 📂 Project Structure

```text
HealthScan-AI/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── screenshots/
│   │   ├── dashboard.png
│   │   ├── vitals-trends.png
│   │   ├── add-vitals.png
│   │   └── medical-report.png
│   ├── package.json
│   └── vite.config.js
├── backend/
│   ├── app.py
│   └── other backend files
└── README.md
```

*Note: The structure above is illustrative. Adjust it to match your actual files.*

## ⚙️ Installation and Setup

### Prerequisites

- Node.js and npm
- Python 3
- pip
- MySQL, if required by your backend configuration

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd HealthScan-AI
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with your actual GitHub repository URL.

### 2. Set Up the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the local URL shown in your terminal, usually
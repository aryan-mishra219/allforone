LIVE LINK : https://allforone-8zta.onrender.com/

# Finance Advisor - Smart Debt Repayment Planner 💰

A high-precision financial management dashboard that uses the **Hybrid Strategy (Snowball + Avalanche)** to help users pay off debts faster. Features AI-powered financial coaching and automated debt lifecycle management.

## 🚀 Quick Start (with Antigravity AI)
If you are using the **Antigravity AI Coding Assistant**, simply give it this prompt:
> "Analyze this repository and set it up for me. Create a virtual environment, install dependencies, set up the .env file from the example, run migrations, and start the server. Ask me for the GROQ_API_KEY if needed."

## 🛠️ Manual Setup

### 1. Environment Preparation
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
1. Copy `.env.example` to a new file named `.env`.
2. Generate a `SECRET_KEY` and provide your `GROQ_API_KEY`.

### 3. Database Initialization
```powershell
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run the App
```powershell
python manage.py runserver
```

## ✨ Key Features
- **High-Precision Calculations**: Built with Python `Decimal` to avoid floating-point errors.
- **Automated Archiving**: Debts are automatically moved to a "Completed" section once paid.
- **AI Coach**: Integrated Groq-powered AI for personalized financial advice.
- **Interactive Planner**: Dynamic month-by-month repayment schedule.

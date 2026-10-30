# 🚀 LeadFlow AI
### AI-Powered Lead Information Validation, CRM Automation & Personalized Email System

LeadFlow AI is an intelligent lead management and automation system that streamlines customer inquiry processing using Large Language Models (LLMs), structured data validation, workflow orchestration, and automated email communication.

The system extracts customer information from inquiries, identifies missing required details, collects additional information through dynamic follow-up forms, updates CRM records, and automatically generates and sends personalized emails once all required information is available.

---

## 🎯 Problem Statement

Businesses receive customer inquiries through websites and other communication channels. Manually reviewing inquiries, collecting missing information, maintaining CRM records, and preparing personalized responses can create repetitive operational work.

LeadFlow AI addresses this problem through an AI-powered workflow that automates customer information extraction, validation, CRM updates, and email communication.

## ✨ Key Features

- **AI-Powered Information Extraction:** Uses Groq LLM to extract structured customer information from natural language inquiries.
- **Automated Information Validation:** Uses Pydantic to validate required customer fields.
- **Dynamic Follow-up Forms:** Identifies missing information and requests clarification from customers.
- **Intelligent CRM Management:** Creates and updates customer records using SQLite.
- **Duplicate Prevention:** Updates existing customer records instead of creating duplicate entries for follow-up submissions.
- **AI Email Generation:** Generates personalized emails based on verified customer-provided information.
- **Automatic Email Delivery:** Sends completed customer emails using Gmail SMTP.
- **Workflow Orchestration:** Uses LangGraph to manage the end-to-end lead processing workflow.
- **CRM Dashboard:** Provides lead information, workflow status, email status, and activity history through Streamlit.
- **Audit History:** Maintains records of important lead and workflow activities.

## 🏗️ System Architecture

```text
              CUSTOMER
                  |
                  v
          FastAPI Customer Form
                  |
                  v
          Groq LLM Extraction
                  |
                  v
          Pydantic Validation
                  |
                  v
        Required Information Check
                  |
           +------+------+
           |             |
      Information     Information
       Missing         Complete
           |             |
           v             |
      Follow-up Form     |
           |             |
           v             |
      Customer Details   |
           |             |
           +------+------+
                  |
                  v
          LangGraph Workflow
                  |
                  v
             SQLite CRM
                  |
                  v
          Groq Email Generation
                  |
                  v
             Gmail SMTP
                  |
                  v
          Customer Email Sent
                  |
                  v
         Streamlit CRM Dashboard
```

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend Framework | FastAPI |
| Frontend Dashboard | Streamlit |
| Large Language Model | Groq |
| Data Validation | Pydantic |
| Workflow Orchestration | LangGraph |
| Database | SQLite |
| Email Integration | Gmail SMTP |
| Data Processing | Pandas |
| Environment Management | Python dotenv |

## 📂 Project Structure

```text
LeadFlow_AI/
│
├── leadflow/
│   ├── templates/
│   │   ├── index.html
│   │   └── follow_up.html
│   │
│   ├── __init__.py
│   ├── agent.py
│   ├── agent_state.py
│   ├── approval.py
│   ├── config.py
│   ├── crm.py
│   ├── dashboard.py
│   ├── database.py
│   ├── email_generator.py
│   ├── email_sender.py
│   ├── graph.py
│   ├── llm.py
│   └── models.py
│
├── data/
│   └── (Database files generated locally)
│
├── tests/
│
├── docs/
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## ⚙️ Installation and Setup

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd LeadFlow_AI
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

### 3. Activate the Environment

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the project root using `.env.example` as a template.

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=your_groq_model_name

GMAIL_ADDRESS=your_gmail_address
GMAIL_APP_PASSWORD=your_gmail_app_password

DATABASE_PATH=data/leadflow.db
```

**Configuration requirements:**

- Obtain a Groq API key from the Groq developer platform.
- Configure Gmail SMTP credentials using a Gmail App Password.
- Never expose API keys or email credentials in source code or public repositories.

## ▶️ Running the Application

The application has two components: FastAPI backend and Streamlit dashboard.

### 1. Start FastAPI Backend

Open the first terminal:

```bash
uvicorn app:app --reload
```

Customer application:

http://127.0.0.1:8000

API documentation:

http://127.0.0.1:8000/docs

### 2. Start Streamlit Dashboard

Open a second terminal and activate the virtual environment.

```bash
streamlit run leadflow/dashboard.py
```

Dashboard:

http://localhost:8501

## 🔄 End-to-End Workflow

**Step 1 — Customer Inquiry**

A customer submits an inquiry through the FastAPI customer form.

**Step 2 — AI Information Extraction**

Groq LLM extracts customer details and converts the natural language inquiry into structured information.

**Step 3 — Information Validation**

Pydantic validates the extracted information against the required fields.

**Step 4 — Missing Information Detection**

If required information is missing, the system requests clarification through a follow-up form.

**Step 5 — CRM Update**

Once the customer provides the missing information, the existing CRM record is updated.

**Step 6 — Personalized Email Generation**

Groq generates an email using verified customer information and the customer's requirements.

**Step 7 — Automatic Email Delivery**

Gmail SMTP sends the generated email to the customer.

**Step 8 — Dashboard Monitoring**

The Streamlit dashboard displays customer information, workflow status, email delivery status, and audit history.

## 📊 Dashboard Features

The Streamlit dashboard provides:

- Total customer leads.
- Leads awaiting information.
- Emails successfully sent.
- Failed email deliveries.
- CRM lead table.
- Individual customer details.
- Generated email content.
- Workflow status.
- Email status.
- Lead activity and audit history.

## 🔐 Security Considerations

- API credentials are stored in environment variables.
- `.env` and local database files are excluded through `.gitignore`.
- Customer data should not be exposed in public repositories.
- Gmail SMTP credentials must be protected.
- Email delivery should be tested using authorized recipient addresses.
- LLM-generated content should be validated before external communication.

## 🧪 Proof of Concept Validation

The prototype has been exercised using two customer inquiry scenarios:

| Test Scenario | Expected Behaviour |
|---|---|
| Incomplete customer inquiry | Detect missing information and open follow-up form |
| Follow-up submission | Update the existing CRM record |
| Complete customer inquiry | Continue without requesting follow-up |
| Email generation | Generate personalized customer email |
| Email delivery | Send through Gmail SMTP |
| Dashboard monitoring | Display CRM and workflow updates |

These are functional demonstration scenarios, not statistically measured model accuracy or production performance benchmarks.

## 🚀 Future Enhancements

Potential future improvements include:

- CRM platform integrations.
- Advanced analytics and reporting.
- Multi-channel customer inquiry support.
- Improved email personalization.
- Role-based dashboard access.
- Production monitoring and deployment.
- More comprehensive automated testing.

## 💡 Business Value

LeadFlow AI demonstrates how AI-powered automation can streamline customer inquiry processing, reduce repetitive manual data entry, improve CRM record consistency, and automate personalized customer communication.

The project serves as a functional proof of concept for intelligent lead management and workflow automation.

---

**Project:** LeadFlow AI  
**Category:** AI/ML | Generative AI | CRM Automation | Workflow Automation  
**Developed Using:** Python, Groq, FastAPI, LangGraph, SQLite and Streamlit
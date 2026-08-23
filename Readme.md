# ApertureHire

AI-powered recruitment platform that helps hiring teams evaluate technical assignments, generate candidate reports, rank applicants, and manage approval-based hiring workflows.

---

## Overview

ApertureHire streamlines technical hiring by combining assignment management, AI-powered evaluation, automated report generation, and HR approval workflows into a single platform.

Instead of manually reviewing every submission, recruiters can upload candidate resumes, distribute assignments, receive AI-generated evaluations, and make final hiring decisions through an approval-based workflow.

---

## Key Features

### Candidate Management
- Create recruitment campaigns
- Upload candidate resumes
- Manage candidate profiles
- Track candidate progress throughout the hiring process

### Assignment Workflow
- Generate assignment links
- Send assignment invitations via email
- Candidate submission portal
- Assignment deadline management
- PDF submission support

### AI-Powered Evaluation
- Automated assignment evaluation using LLMs
- Question-wise scoring
- Technical competency assessment
- Requirement coverage analysis
- Reasoning quality evaluation
- Hiring recommendations

### HR Review & Approval
- Review AI-generated reports
- Rank candidates by score
- Threshold-based candidate selection
- Top-N candidate selection
- Manual approval before final decisions
- Override AI recommendations when needed

### Report Generation
- Detailed PDF evaluation reports
- Per-question feedback
- Strengths and weaknesses analysis
- Candidate score breakdown
- Recruiter-friendly summaries

### Storage Management
Supports both Local Storage and AWS S3.

Storage structure:

```text
campaigns/
└── campaign_id/
    └── candidate_id/
        ├── resume.pdf
        ├── submission.pdf
        └── report.pdf
```

### Email Automation
- Assignment invitation emails
- Submission notifications
- Final selection emails
- Final rejection emails

---

## System Workflow

```text
HR Uploads Resume
        │
        ▼
Candidate Created
        │
        ▼
Assignment Sent via Email
        │
        ▼
Candidate Opens Submission Portal
        │
        ▼
Candidate Uploads Assignment
        │
        ▼
AI Evaluation
        │
        ▼
PDF Report Generation
        │
        ▼
HR Review & Approval
        │
        ▼
Final Selection / Rejection
        │
        ▼
Email Notification
```

---

## Architecture

```text
Frontend (React + TypeScript)
            │
            ▼
      FastAPI Backend
            │
 ┌──────────┼──────────┐
 ▼          ▼          ▼
SQLite      S3      LLM Provider
Database   Storage   Evaluation
```

---

## Tech Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- React Router

### Backend
- FastAPI
- SQLAlchemy
- Pydantic
- PyMuPDF

### AI & Evaluation
- LangChain
- LangSmith
- OpenAI / Azure OpenAI

### Storage
- Local Storage
- AWS S3

### DevOps
- Docker
- GitHub Actions
- Render
- Vercel

### Monitoring
- MLflow
- LangSmith

---

## Local Development

### Clone Repository

```bash
git clone https://github.com/barnwalakash60973-pixel/ApertureHire.git
cd ApertureHire
```

---

### Backend Setup

```bash
cd backend

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file:

```env
# Public URLs
FRONTEND_PUBLIC_URL=http://localhost:5173
BACKEND_PUBLIC_URL=http://localhost:8000

# Storage
STORAGE_BACKEND=local
LOCAL_STORAGE_DIR=./data/storage

# Application
MAX_UPLOAD_MB=15
LOG_LEVEL=INFO
MAX_CONCURRENT_LLM_CALLS=4

# Retention
REJECTED_CANDIDATE_RETENTION_DAYS=60
```

Run backend:

```bash
uvicorn app.main:app --reload
```

API:

```text
http://localhost:8000
```

Swagger Docs:

```text
http://localhost:8000/docs
```

---

### Frontend Setup

```bash
cd frontend

npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

## Docker

Build image:

```bash
docker build -t aperturehire .
```

Run container:

```bash
docker run -p 8000:8000 aperturehire
```

---

## Deployment

### Backend (Render)

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Frontend (Vercel)

Build Command:

```bash
npm run build
```

Output Directory:

```text
dist
```

---

## CI/CD

GitHub Actions automatically:

- Runs backend tests
- Runs frontend build
- Builds Docker image
- Triggers deployment

Workflow location:

```text
.github/workflows/ci-cd.yml
```

---

## Future Enhancements

- DVC data versioning
- Interview scheduling
- Multi-tenant support
- Role-based access control (RBAC)
- Analytics dashboard
- Advanced recruiter insights
- Candidate comparison reports

---

## Author

**Akash Kumar Barnwal**

M.Sc. Artificial Intelligence & Machine Learning  
IIIT Lucknow

GitHub: https://github.com/barnwalakash60973-pixel

---

## License

This project is licensed under the MIT License.
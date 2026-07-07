# Module 7 — Cloud Computing: S3 + SageMaker + EC2 Deployment

This module connects the Grad Café dataset to AWS cloud services:
1. **Part 1:** Upload data to S3 and download it into a SageMaker notebook using boto3
2. **Part 2:** Deploy the Module 6 microservice stack to an EC2 instance

---

## Folder Structure

```
module_7/
├── grad-cafe-pipeline.ipynb    # SageMaker notebook
├── s3_fetch.py                 # Reusable boto3 S3 download logic
├── requirements.txt            # Python dependencies
├── README.md
├── mfa.png                     # Root MFA screenshot
├── dailyWork.png               # IAM user permissions screenshot
├── grad-cafe-bucket.png        # S3 bucket contents screenshot
├── liveNotebook.png            # SageMaker InService screenshot
├── ec2-instance.png            # EC2 instance running screenshot
├── ec2-security-group.png      # Security group rules screenshot
├── ec2-compose-ps.png          # docker compose ps output screenshot
├── ec2-app.png                 # Live app at EC2 IP screenshot
└── ec2/
    ├── docker-compose.ec2.yml  # EC2-adapted compose file
    └── EC2_DEPLOYMENT.md       # Exact deployment steps
```

---

## Part 1: S3 → SageMaker Pipeline

### Prerequisites
- AWS account with IAM user `dailyWork-SS`
- S3 bucket `grad-cafe-ss` with `llm_extend_applicant_data.json` uploaded
- SageMaker notebook instance `s3-to-sagemaker-grad-cafe-pipeline` (ml.t2.medium)
- Access keys for `dailyWork-SS` (downloaded as CSV)

### Dependencies
```bash
pip install -r requirements.txt
```

### How to Run the Notebook

1. Open SageMaker notebook instance in AWS Console
2. Click **Open Jupyter**
3. Upload `s3_fetch.py` and `grad-cafe-pipeline.ipynb`
4. Set environment variables before running:
   ```python
   import os
   os.environ['AWS_ACCESS_KEY_ID'] = 'your-access-key'
   os.environ['AWS_SECRET_ACCESS_KEY'] = 'your-secret-key'
   os.environ['AWS_DEFAULT_REGION'] = 'us-east-2'
   ```
5. Run all cells — `applicant_data_SM.json` will be saved locally in SageMaker

### Output
- Downloaded file: `applicant_data_SM.json` (saved in `/home/ec2-user/SageMaker/`)
- Contains 30,000 applicant records from the Grad Café dataset

### S3 Download Logic
Reusable boto3 logic lives in `s3_fetch.py`:
- `get_s3_client()` — creates boto3 client from environment credentials
- `download_applicant_data()` — downloads from S3 and saves locally

**Never hardcode AWS credentials. Always load from environment variables.**

---

## Part 2: EC2 Deployment

The Module 6 microservice stack is deployed on EC2 using Docker Compose.
See `ec2/EC2_DEPLOYMENT.md` for exact deployment steps.

### Quick Start
```bash
ssh -i /path/to/module7-key.pem ubuntu@13.58.35.53
cd module7
docker compose -f docker-compose.ec2.yml --env-file .env up -d
```

### Live App
- Web dashboard: http://13.58.35.53:8080
- Docker Hub images: https://hub.docker.com/r/scharfshutzer/module_6

---

## AWS Resources

| Resource | Name | Status |
|----------|------|--------|
| S3 Bucket | grad-cafe-ss | Active |
| SageMaker | s3-to-sagemaker-grad-cafe-pipeline | **Stopped after completion** |
| EC2 | module-7-ec2 | **Stopped after completion** |

**Important: SageMaker and EC2 instances have been stopped after assignment
completion to avoid charges. Infrastructure is preserved for Module 8.**

---

## Security Notes
- Root account protected with MFA (Passkey)
- IAM user `dailyWork-SS` used for all day-to-day work
- AWS credentials never hardcoded or committed to git
- Only `.env.example` included in git (not `.env`)
- EC2 security group restricts SSH and port 8080 to student IP only
- PostgreSQL (5432) and RabbitMQ (15672) not exposed publicly
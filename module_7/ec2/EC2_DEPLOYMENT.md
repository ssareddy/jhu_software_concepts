# EC2 Deployment Guide — Module 7

## Instance Details
- **AMI:** Ubuntu 24.04 LTS
- **Instance type:** t3.micro
- **Public IPv4:** 13.58.35.53
- **Security group:** SSH (22) and port 8080 restricted to student IP only

## Steps Taken

### 1. Launch EC2 Instance
- Launched Ubuntu 24.04 LTS t3.micro via AWS Console
- Created key pair `module7-key.pem`
- Security group inbound rules:
  - SSH (22): My IP only
  - Custom TCP (8080): My IP only
  - PostgreSQL (5432): NOT exposed
  - RabbitMQ (15672): NOT exposed

### 2. SSH Into Instance
```bash
ssh -i /path/to/module7-key.pem ubuntu@13.58.35.53
```

### 3. Install Docker and Docker Compose
```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo apt-get install -y docker-compose-v2
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

### 4. Create Project Directory
```bash
mkdir -p module7
cd module7
```

### 5. Create Environment File
```bash
cat > .env << 'ENVEOF'
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-password>
POSTGRES_DB=gradcafe
DATABASE_URL=postgresql://postgres:<your-password>@db:5432/gradcafe
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
FLASK_ENV=production
SEED_JSON=/data/llm_extend_applicant_data.json
TARGET_TABLE=applicants
ID_KEY=url
ENVEOF
```

### 6. Create docker-compose.ec2.yml
```bash
cat > docker-compose.ec2.yml << 'COMPOSEEOF'
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

  rabbitmq:
    image: rabbitmq:3.13-management
    healthcheck:
      test: ["CMD-SHELL", "rabbitmq-diagnostics -q ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  web:
    image: scharfshutzer/module_6:web
    environment:
      FLASK_ENV: ${FLASK_ENV}
      DATABASE_URL: ${DATABASE_URL}
      RABBITMQ_URL: ${RABBITMQ_URL}
    ports:
      - "8080:8080"
    depends_on:
      db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  worker:
    image: scharfshutzer/module_6:worker
    environment:
      DATABASE_URL: ${DATABASE_URL}
      RABBITMQ_URL: ${RABBITMQ_URL}
      SEED_JSON: ${SEED_JSON}
      TARGET_TABLE: ${TARGET_TABLE}
      ID_KEY: ${ID_KEY}
    depends_on:
      db:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

volumes:
  pgdata:
COMPOSEEOF
```

### 7. Deploy the Stack
```bash
docker compose -f docker-compose.ec2.yml --env-file .env up -d
docker compose -f docker-compose.ec2.yml ps
```

### 8. Verify
- Flask app reachable at: http://13.58.35.53:8080
- Pull Data and Update Analysis buttons verified working
- Worker processes tasks via RabbitMQ

### 9. Initialize Database Schema
```bash
docker compose -f docker-compose.ec2.yml exec db psql -U postgres -d gradcafe -c "
CREATE TABLE IF NOT EXISTS applicants (...);
CREATE TABLE IF NOT EXISTS ingestion_watermarks (...);
CREATE TABLE IF NOT EXISTS analytics_cache (...);"
```

## Ports
| Service | Internal Port | External Port | Exposed |
|---------|--------------|---------------|---------|
| web | 8080 | 8080 | Yes (My IP only) |
| db | 5432 | — | No |
| rabbitmq | 5672/15672 | — | No |
| worker | — | — | No |

## Troubleshooting
- If worker fails to connect to RabbitMQ on startup, it retries every 5 seconds automatically
- If web shows "relation does not exist", run the DB schema initialization command above
- Docker images pulled from: https://hub.docker.com/r/scharfshutzer/module_6

## Cleanup
```bash
# Stop the stack (do NOT delete — needed for Module 8)
docker compose -f docker-compose.ec2.yml down

# Stop EC2 instance from AWS Console
# Stop SageMaker instance from AWS Console
```

**Note: AWS resources (EC2 and SageMaker) have been stopped after assignment completion
to avoid unnecessary charges. Infrastructure is preserved for Module 8.**
# 🚀 Serverless ChatOps RDS-to-S3 Data Export Pipeline

![AWS](https://img.shields.io/badge/AWS-Cloud-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Slack](https://img.shields.io/badge/Slack-ChatOps-4A154B?style=for-the-badge&logo=slack&logoColor=white)

## 📌 Project Overview

In modern cloud environments, developers and data analysts often need on-demand database exports without being granted direct network access or master credentials to production databases.

This project implements a **fully automated, serverless, event-driven ChatOps pipeline** on AWS. Using a simple Slack slash command (`/export-data db1` or `/export-data db2`), authorized users can trigger an on-demand data export from specific **Amazon RDS MySQL** databases directly into an **Amazon S3** bucket as CSV files.

The architecture runs with **zero idle compute cost** by spinning up ephemeral **AWS Fargate** containers orchestrated via **AWS Step Functions**, while securing all database credentials inside **AWS Systems Manager (SSM) Parameter Store**.

---

## 🏗️ Architecture & Workflow

```text
+-------------+       +------------------+       +-------------------+
|  Slack App  | ----> | AWS API Gateway  | ----> |    AWS Lambda     |
| (/export)   |       | (POST /export)   |       | (Webhook Handler) |
+-------------+       +------------------+       +---------+---------+
                                                           |
                                                           | Passes {"target_db": "db1"}
                                                           v
+-------------+       +------------------+       +-------------------+
|  Amazon S3  | <---- | Amazon ECS       | <---- | AWS Step Functions|
|  (CSV File) |       | Fargate Task     |       | (State Machine)   |
+-------------+       +--------+---------+       +-------------------+
                               |                           ^
                               | Queries Data              | Injects Secrets
                               v                           |
                      +------------------+       +-------------------+
                      | Amazon RDS MySQL |       | AWS SSM Parameter |
                      | (db1 & db2)      |       | Store (Secrets)   |
                      +------------------+       +-------------------+
```

### How It Works Step-by-Step

1. **User Trigger (Slack):** A user runs `/export-data db1` or `/export-data db2` in a designated Slack channel.
2. **API Layer (API Gateway):** Slack sends an HTTP POST payload to an Amazon API Gateway endpoint.
3. **Ingestion & Validation (AWS Lambda):** API Gateway invokes a Python Lambda function. Because Slack requires an HTTP response within 3 seconds, Lambda parses the database name, asynchronously triggers the Step Functions workflow, and immediately returns a `200 OK` status message to Slack.
4. **Workflow Orchestration (AWS Step Functions):** The State Machine launches an Amazon ECS Fargate task using the `.sync` integration pattern (waiting for the container to complete execution) and dynamically overrides the `TARGET_DB` environment variable with the user's input.
5. **Secret Injection (AWS SSM Parameter Store):** During container startup, ECS securely fetches `DB_HOST`, `DB_USER`, and the KMS-encrypted `DB_PASSWORD` from SSM Parameter Store and injects them into the container environment.
6. **Batch Processing (ECS Fargate + Docker):** The Python container connects to the RDS MySQL instance, queries the target database (`db1.customers` or `db2.transactions`), writes the records into a CSV file, uploads it to Amazon S3 (`db1-export.csv` or `db2-export.csv`), and exits cleanly with `sys.exit(0)`.

---

## 🛠️ Tech Stack & AWS Services Used

| Category | Services / Tools |
|---|---|
| **Compute** | Amazon ECS (AWS Fargate Serverless Engine), AWS Lambda |
| **Orchestration** | AWS Step Functions |
| **API & Integration** | Amazon API Gateway (HTTP API), Slack Slash Commands |
| **Database & Storage** | Amazon RDS (MySQL 8.x), Amazon S3, Amazon ECR (Container Registry) |
| **Security & Networking** | AWS IAM (Least-Privilege Roles), AWS SSM Parameter Store, AWS KMS, VPC, Subnets, Security Groups |
| **Languages & Tools** | Python 3 (`pymysql`, `boto3`), Docker, Bash, AWS CLI |

---

## 📋 Complete Step-by-Step Implementation Guide

Follow these steps from start to finish to replicate this project in your own AWS account.

### Step 1: Configure Amazon RDS (MySQL) & Sample Databases

1. Create an Amazon RDS MySQL instance inside your VPC (`rds-exporter-db`).
2. Configure the RDS Security Group to allow inbound traffic on port `3306` from your Fargate task security group.
3. Connect to the RDS instance using the MySQL CLI:

```bash
mysql -h <YOUR_RDS_ENDPOINT> -P 3306 -u admin -p
```

4. Create two distinct databases (`db1` and `db2`) and populate them with sample tables:

```sql
CREATE DATABASE db1;
USE db1;
CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    city VARCHAR(50),
    account_status VARCHAR(20) DEFAULT 'ACTIVE'
);
INSERT INTO customers (full_name, email, city, account_status) VALUES
('Hamza Javed', 'hamza@example.com', 'Lahore', 'ACTIVE'),
('Ali Khan', 'ali.khan@example.com', 'Karachi', 'ACTIVE');

CREATE DATABASE db2;
USE db2;
CREATE TABLE transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    reference_no VARCHAR(50) NOT NULL,
    customer_name VARCHAR(100) NOT NULL,
    amount_usd DECIMAL(10, 2) NOT NULL,
    payment_status VARCHAR(20)
);
INSERT INTO transactions (reference_no, customer_name, amount_usd, payment_status) VALUES
('TXN-908101', 'Hamza Javed', 1850.00, 'COMPLETED'),
('TXN-908102', 'Ali Khan', 240.00, 'COMPLETED');
```

### Step 2: Create the Amazon S3 Bucket

1. Open the Amazon S3 Console and create a private bucket (e.g., `ecs-rds-exporter`).
2. Keep **Block all public access** enabled for security.

### Step 3: Store Database Credentials in AWS SSM Parameter Store

Instead of hardcoding database credentials in the container or Task Definition, store them securely in **AWS Systems Manager → Parameter Store**:

| Parameter Name | Type | Value |
|---|---|---|
| `/rds-exporter/DB_HOST` | String | Your RDS Endpoint URL |
| `/rds-exporter/DB_USER` | String | `admin` |
| `/rds-exporter/DB_PASSWORD` | SecureString | Your RDS Master Password (encrypted via AWS KMS) |

### Step 4: Build & Push the Docker Container to Amazon ECR

Create `requirements.txt`:

```text
pymysql
boto3
```

Create `main.py` to dynamically connect to the requested database (`TARGET_DB`), export the table to `/tmp/<db>-export.csv`, upload it to S3, and terminate with `sys.exit(0)`.

Create the `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["python", "main.py"]
```

Authenticate Docker with Amazon ECR, build the image, and push it:

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

docker build -t ecs-rds-exporter-repo .

docker tag ecs-rds-exporter-repo:latest <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ecs-rds-exporter-repo:latest

docker push <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ecs-rds-exporter-repo:latest
```

### Step 5: Configure IAM Roles & ECS Fargate Task Definition

**IAM Roles Separation:**

- **`ECSTaskExecutionRole`**: Grants the ECS agent permission to pull images from ECR, push logs to CloudWatch, and read secrets from SSM Parameter Store (`AmazonSSMReadOnlyAccess`).
- **`ECSTaskS3UploadRole` (Task Role)**: Grants the running Python application permission to upload objects to the target S3 bucket (`s3:PutObject`).

**ECS Cluster & Task Definition:**

1. Create an AWS Fargate Cluster (`ecs-rds-cluster`).
2. Create a Task Definition (`ecs-rds-exporter-task`).
3. Under Environment Variables, pass `S3_BUCKET` as a standard **Value**, and inject `DB_HOST`, `DB_USER`, and `DB_PASSWORD` using **ValueFrom** referencing their SSM Parameter Store ARNs.

### Step 6: Create the AWS Step Functions State Machine

Create a State Machine (`rds-exporter-state-machine`) that runs the ECS task synchronously (`ecs:runTask.sync`) and dynamically overrides the `TARGET_DB` environment variable using the payload passed by AWS Lambda:

```json
{
  "Comment": "Dynamic RDS MySQL to S3 Exporter",
  "StartAt": "RunExportTask",
  "States": {
    "RunExportTask": {
      "Type": "Task",
      "Resource": "arn:aws:states:::ecs:runTask.sync",
      "Parameters": {
        "LaunchType": "FARGATE",
        "Cluster": "arn:aws:ecs:us-east-1:<AWS_ACCOUNT_ID>:cluster/ecs-rds-cluster",
        "TaskDefinition": "arn:aws:ecs:us-east-1:<AWS_ACCOUNT_ID>:task-definition/ecs-rds-exporter-task:14",
        "NetworkConfiguration": {
          "AwsvpcConfiguration": {
            "Subnets": [
              "subnet-xxxxxxxxxxxxxxxxx",
              "subnet-yyyyyyyyyyyyyyyyy"
            ],
            "SecurityGroups": [
              "sg-zzzzzzzzzzzzzzzzz"
            ],
            "AssignPublicIp": "ENABLED"
          }
        },
        "Overrides": {
          "ContainerOverrides": [
            {
              "Name": "rds-exporter-container",
              "Environment": [
                {
                  "Name": "TARGET_DB",
                  "Value.$": "$.target_db"
                }
              ]
            }
          ]
        }
      },
      "End": true
    }
  }
}
```

### Step 7: Create AWS Lambda & API Gateway (Slack Webhook)

1. Create a Python AWS Lambda function (`trigger-rds-exporter`) with IAM permissions for `states:StartExecution`.
2. The Lambda function parses the `application/x-www-form-urlencoded` payload sent by Slack, extracts the text argument (`db1` or `db2`), triggers the Step Functions State Machine, and returns an immediate Slack-formatted JSON message.
3. Create an Amazon API Gateway (HTTP API) with a `POST /export` route integrated with the Lambda function.

### Step 8: Configure the Slack Slash Command

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new Slack App in your workspace.
2. Navigate to **Slash Commands** and click **Create New Command**:
   - **Command:** `/export-data`
   - **Request URL:** `https://<API_GATEWAY_ID>.execute-api.us-east-1.amazonaws.com/export`
   - **Usage Hint:** `[db1 | db2]`
3. Install the app to your workspace and test it inside your channel:

```text
/export-data db1
/export-data db2
```

---

## 🔒 Security & Cost-Optimization Highlights

- **Zero Hardcoded Secrets:** Database credentials are removed from code and Task Definitions and fetched dynamically at runtime via AWS SSM Parameter Store.
- **Scale-to-Zero Compute:** Unlike an EC2 instance running 24/7, the ECS Fargate task spins up only when requested and terminates immediately via `sys.exit(0)` once the S3 upload completes.
- **Least-Privilege IAM:** Execution permissions (ECR/SSM/CloudWatch) are strictly separated from application runtime permissions (S3 upload).

---

## 👤 Author

**Hamza Javed**
Cloud & DevOps Engineer

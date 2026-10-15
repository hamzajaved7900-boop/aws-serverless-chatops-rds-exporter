import os
import sys
import csv
import pymysql
import boto3

DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
S3_BUCKET = os.environ.get('S3_BUCKET')

# Environment variable se target database ka naam uthayega (Default: db1)
TARGET_DB = os.environ.get('TARGET_DB', 'db1').strip().lower()

print(f"Connecting to database: {TARGET_DB}")

try:
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=TARGET_DB,
        cursorclass=pymysql.cursors.DictCursor
    )

    with connection.cursor() as cursor:
        if TARGET_DB == 'db1':
            print("Querying table: customers from db1")
            cursor.execute("SELECT * FROM customers;")
        elif TARGET_DB == 'db2':
            print("Querying table: transactions from db2")
            cursor.execute("SELECT * FROM transactions;")
        else:
            print(f"Unknown database: {TARGET_DB}")
            sys.exit(1)

        rows = cursor.fetchall()

    if not rows:
        print(f"No records found in database {TARGET_DB}.")
        sys.exit(0)

    # File names dynamic banayein: db1-export.csv ya db2-export.csv
    local_file = f"/tmp/{TARGET_DB}-export.csv"
    s3_file_key = f"{TARGET_DB}-export.csv"

    print(f"Writing {len(rows)} rows to {local_file}...")
    with open(local_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Uploading {local_file} to S3 bucket {S3_BUCKET} as {s3_file_key}...")
    s3_client = boto3.client('s3')
    s3_client.upload_file(local_file, S3_BUCKET, s3_file_key)
    print(f"Successfully uploaded {s3_file_key} to s3://{S3_BUCKET}/")
    sys.exit(0)

except Exception as e:
    print(f"Error during export: {e}")
    sys.exit(1)
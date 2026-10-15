import json
import boto3
import urllib.parse

sfn_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = "arn:aws:states:us-east-1:337774319478:stateMachine:rds-exporter-state-machine"

def lambda_handler(event, context):
    try:
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            import base64
            body = base64.b64decode(body).decode('utf-8')
            
        parsed_body = urllib.parse.parse_qs(body)
        
        # Slack command ke sath likha hua database name extract karein
        raw_text = parsed_body.get('text', ['db1'])[0].strip().lower()
        selected_db = raw_text if raw_text in ['db1', 'db2'] else 'db1'
        
        # Step Functions ko selected database pass karein
        execution_input = json.dumps({
            "target_db": selected_db
        })
        
        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=execution_input
        )
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "response_type": "in_channel",
                "text": f"🚀 *RDS to S3 Export Triggered for `{selected_db}`!*\nProcessing `{selected_db}` data export. The file `{selected_db}-export.csv` will be available in S3 shortly."
            })
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "response_type": "ephemeral",
                "text": f"❌ Error: {str(e)}"
            })
        }
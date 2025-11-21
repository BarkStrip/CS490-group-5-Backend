import boto3
import os
from botocore.exceptions import NoCredentialsError


def upload_file_to_s3(file, filename, bucket_name):

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
    )
    try:
        s3.upload_fileobj(file, bucket_name, filename, ExtraArgs={"ACL": "public-read"})
        base_url = os.getenv("S3_BASE_URL")
        generated_url = f"{base_url}/{filename}"

        return generated_url

    except NoCredentialsError:

        raise Exception("AWS credentials not found. Check environment variables.")
    except Exception as e:

        raise e

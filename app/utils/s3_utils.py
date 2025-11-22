import boto3
import os
from botocore.exceptions import NoCredentialsError
from urllib.parse import urlparse


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


def delete_file_from_s3(image_url, bucket_name):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION"),
    )

    try:
        parsed = urlparse(image_url)
        key = parsed.path.lstrip("/")

        s3.delete_object(Bucket=bucket_name, Key=key)
        return True

    except NoCredentialsError:
        raise Exception("AWS credentials not found. Check environment variables.")
    except Exception as e:
        print(f"Error deleting file from S3: {e}")
        return False

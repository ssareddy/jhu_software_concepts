"""
s3_fetch.py
-----------
Reusable boto3 logic for downloading applicant data from S3.

Credentials are loaded from environment variables or AWS config file —
never hardcoded. Set the following environment variables before running:

    AWS_ACCESS_KEY_ID=<your-access-key>
    AWS_SECRET_ACCESS_KEY=<your-secret-key>
    AWS_DEFAULT_REGION=us-east-2
"""
import os
import boto3


BUCKET_NAME = "grad-cafe-ss"
S3_KEY = "llm_extend_applicant_data.json"
LOCAL_OUTPUT = "applicant_data_SM.json"


def get_s3_client():
    """
    Create and return a boto3 S3 client using environment credentials.

    Reads AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and
    AWS_DEFAULT_REGION from the environment. Raises if credentials
    are not set.
    """
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
    return boto3.client("s3", region_name=region)


def download_applicant_data(
    bucket: str = BUCKET_NAME,
    s3_key: str = S3_KEY,
    local_path: str = LOCAL_OUTPUT,
) -> str:
    """
    Download applicant data JSON from S3 and save it locally.

    Parameters
    ----------
    bucket : str
        S3 bucket name.
    s3_key : str
        S3 object key (filename in the bucket).
    local_path : str
        Local file path to save the downloaded file.

    Returns
    -------
    str
        Absolute path of the saved local file.
    """
    client = get_s3_client()
    client.download_file(bucket, s3_key, local_path)
    abs_path = os.path.abspath(local_path)
    print(f"Downloaded s3://{bucket}/{s3_key} -> {abs_path}")
    return abs_path


if __name__ == "__main__":
    download_applicant_data()

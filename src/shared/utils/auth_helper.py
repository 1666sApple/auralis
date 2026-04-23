import os
import boto3
from botocore.config import Config

from src.shared.config.settings import settings
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)

for var in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"]:
    if var in os.environ:
        logger.info(f"Removing environment variable '{var}' to prevent proxy connection.")
        del os.environ[var]


def get_boto3_client(
    service_name: str, 
    region_name: str, 
    max_attempts: int = 2, 
    read_timeout: int = 360, 
    connect_timeout: int = 60
):
    """Create a boto3 client strictly using .env AWS credentials."""
    
    access_key = settings.AWS_ACCESS_KEY_ID
    secret_key = settings.AWS_SECRET_ACCESS_KEY
    
    if not access_key or not secret_key:
        raise ValueError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in your .env file.")

    retry_config = Config(
        read_timeout=read_timeout,
        connect_timeout=connect_timeout,
        retries={'max_attempts': max_attempts}
    )
    
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region_name,
    )
    
    return session.client(service_name, config=retry_config)
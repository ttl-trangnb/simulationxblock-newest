"""
Utility methods for xblock
"""

import concurrent.futures
import logging
import os
import shutil
from zipfile import ZipFile, is_zipfile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage, get_storage_class
import boto3

log = logging.getLogger(__name__)

AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""
AWS_STORAGE_BUCKET_NAME = "vmb-project-data"
AWS_REGION = "ap-southeast-1"
AWS_S3_CUSTOM_DOMAIN = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com"

# Khởi tạo boto3 storage với credentials
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

MAX_WORKERS = getattr(settings, "THREADPOOLEXECUTOR_MAX_WORKERS", 10)

# # Kiểm tra quyền truy cập S3
# def check_s3_access():
#     try:
#         response = s3_client.list_buckets()
#         print("S3 Buckets:", [bucket["Name"] for bucket in response["Buckets"]])
#         return True
#     except Exception as e:
#         print("Error accessing S3:", e)
#         return False


def get_simulation_storage():
    """
    Returns storage for simulation content

    If SIMULATONXBLOCK_STORAGE is defined in django settings, intializes storage using the
    specified settings. Otherwise, returns default_storage.
    """

    # simulation_storage_settings = getattr(settings, "SIMULATONXBLOCK_STORAGE", None)
    simulation_storage_settings = {
        "storage_class": "storages.backends.s3boto3.S3Boto3Storage",
        "settings": {
            "bucket_name": "vmb-project-data",
            "querystring_auth": False,
        },
    }

    if not simulation_storage_settings:
        return default_storage

    storage_class_import_path = simulation_storage_settings.get("storage_class", None)
    storage_settings = simulation_storage_settings.get("settings", {})

    storage_class = get_storage_class(storage_class_import_path)

    storage = storage_class(**storage_settings)

    return storage


def str2bool(val):
    """Converts string value to boolean"""
    return val in ["True", "true", "1"]


def delete_path(path):
    if os.path.exists(path):
        shutil.rmtree(path)


def future_result_handler(future):
    """
    Prints results of future in logs
    """
    try:
        log.info("Future task completed: Result:[%s]", future.result())
    except BaseException as exp:
        log.error("Future completed with error %s", exp)


def delete_existing_files_cloud(storage, path):
    """
    Recusively delete all files under given path on cloud storage
    """
    log.info("%s path is being deleted on cloud", path)
    dir_names, file_names = storage.listdir(path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for file_name in file_names:
            file_path = os.path.join(path, file_name)
            future = executor.submit(storage.delete, file_path)
            future.add_done_callback(future_result_handler)

    for dir_name in dir_names:
        dir_path = os.path.join(path, dir_name)
        delete_existing_files_cloud(storage, dir_path)
        
def read_file_from_s3(bucket, file_key):
    """
    Đọc nội dung file từ S3
    """
    response = s3_client.get_object(Bucket=bucket, Key=file_key)
    file_content = response["Body"].read().decode("utf-8")  # Đọc và giải mã UTF-8
    return file_content

def upload_on_cloud(json_file, storage, path):
    """
    Upload it on cloud storage
    """
    # delete_existing_files_cloud(storage, path)
    
    real_path = os.path.join(path, json_file.name)
    log.info(real_path)
    
    if os.path.basename(real_path) in {"", ".", ".."}:
        log.error("Invalid file path: %s", real_path)
        return

    log.info("Uploading to S3: %s", real_path)

    try:
        # Đọc nội dung file trước khi upload
        file_content = json_file.read().decode("utf-8")  # Đọc file thành chuỗi

        # Upload file lên S3
        s3_client.put_object(
            Bucket=AWS_STORAGE_BUCKET_NAME,
            Key=real_path,
            Body=file_content,
            ContentType="application/json"
        )

        log.info("Upload successful: %s", real_path)
        return f"{AWS_S3_CUSTOM_DOMAIN}/{real_path}"
    
    except Exception as e:
        log.error("Upload failed: %s", str(e))
        return None
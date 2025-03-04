import os
import boto3
import psutil
from fastapi import FastAPI, File, UploadFile, HTTPException

app = FastAPI()

# Read configuration from environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
AWS_S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT", "http://minio:9000")
BUCKET_NAME = os.getenv("BUCKET_NAME", "fastapi-bucket")

# Initialize the S3 client to point to MinIO
s3_client = boto3.client(
    "s3",
    endpoint_url=AWS_S3_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name="us-east-1"
)

def get_memory_usage_gb():
    """Returns the current memory usage of the process in GB."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info().rss  # Resident Set Size (bytes)
    return mem_info / (1024 ** 3)  # Convert to GB

@app.post("/upload-s3/")
async def upload_to_s3(file: UploadFile = File(...)):
    key = file.filename  # You can also customize the key name

    # Initiate the multipart upload
    try:
        mpu = s3_client.create_multipart_upload(Bucket=BUCKET_NAME, Key=key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initiating multipart upload: {e}")
    
    upload_id = mpu["UploadId"]
    parts = []
    part_number = 1
    chunk_size = 5 * 1024 * 1024  # 5MB

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break  # End of file reached
            
            mem_usage = get_memory_usage_gb()
            print(f"Memory usage before uploading part {part_number}: {mem_usage:.4f} GB")
            
            response = s3_client.upload_part(
                Bucket=BUCKET_NAME,
                Key=key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=chunk
            )
            
            mem_usage = get_memory_usage_gb()
            print(f"Memory usage after uploading part {part_number}: {mem_usage:.4f} GB")
            
            parts.append({
                "ETag": response["ETag"],
                "PartNumber": part_number
            })
            part_number += 1
        
        # Complete the multipart upload
        s3_client.complete_multipart_upload(
            Bucket=BUCKET_NAME,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts}
        )
    except Exception as e:
        # Abort the multipart upload on error
        s3_client.abort_multipart_upload(Bucket=BUCKET_NAME, Key=key, UploadId=upload_id)
        raise HTTPException(status_code=500, detail=f"Error during file upload: {e}")
    
    return {"message": "Upload successful", "filename": key}
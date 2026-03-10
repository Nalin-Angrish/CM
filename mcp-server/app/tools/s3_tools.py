"""S3 bucket tool implementations using boto3."""
import boto3
from botocore.exceptions import ClientError
from app.validators import validate_bucket_name, validate_region, ValidationError


def _get_s3_client(region: str = "us-east-1"):
    return boto3.client("s3", region_name=region)


def create_s3_bucket(params: dict) -> dict:
    bucket_name = params["bucket_name"]
    region = params.get("region", "us-east-1")
    public_access = params.get("public_access", False)
    versioning = params.get("versioning", False)

    validate_bucket_name(bucket_name)
    validate_region(region)

    if public_access:
        raise ValidationError(
            "Public S3 buckets are blocked by security policy. "
            "Set public_access to false or omit it."
        )

    s3 = _get_s3_client(region)

    try:
        create_args = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_args["CreateBucketConfiguration"] = {
                "LocationConstraint": region
            }
        s3.create_bucket(**create_args)

        # Block all public access
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )

        if versioning:
            s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"},
            )

        return {
            "success": True,
            "cloud_identifier": bucket_name,
            "message": f"S3 bucket '{bucket_name}' created in {region}",
            "details": {
                "bucket_name": bucket_name,
                "region": region,
                "public_access": False,
                "versioning": versioning,
            },
        }
    except ClientError as e:
        return {
            "success": False,
            "message": f"Failed to create bucket: {e.response['Error']['Message']}",
            "details": {"error_code": e.response["Error"]["Code"]},
        }


def modify_s3_bucket(params: dict) -> dict:
    bucket_name = params["bucket_name"]
    validate_bucket_name(bucket_name)

    s3 = _get_s3_client()
    changes = []

    try:
        if "versioning" in params:
            status = "Enabled" if params["versioning"] else "Suspended"
            s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": status},
            )
            changes.append(f"versioning={status}")

        if "public_access" in params:
            if params["public_access"]:
                raise ValidationError("Cannot enable public access per security policy")
            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )
            changes.append("public_access=blocked")

        return {
            "success": True,
            "cloud_identifier": bucket_name,
            "message": f"Bucket '{bucket_name}' modified: {', '.join(changes)}",
            "details": {"changes": changes},
        }
    except ClientError as e:
        return {
            "success": False,
            "message": f"Failed to modify bucket: {e.response['Error']['Message']}",
            "details": {"error_code": e.response["Error"]["Code"]},
        }


def delete_s3_bucket(params: dict) -> dict:
    bucket_name = params["bucket_name"]
    validate_bucket_name(bucket_name)

    s3 = _get_s3_client()

    try:
        # Empty the bucket first (only up to 1000 objects for safety)
        response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1000)
        if "Contents" in response:
            objects = [{"Key": obj["Key"]} for obj in response["Contents"]]
            s3.delete_objects(
                Bucket=bucket_name, Delete={"Objects": objects}
            )

        s3.delete_bucket(Bucket=bucket_name)

        return {
            "success": True,
            "cloud_identifier": bucket_name,
            "message": f"S3 bucket '{bucket_name}' deleted",
            "details": {"bucket_name": bucket_name},
        }
    except ClientError as e:
        return {
            "success": False,
            "message": f"Failed to delete bucket: {e.response['Error']['Message']}",
            "details": {"error_code": e.response["Error"]["Code"]},
        }

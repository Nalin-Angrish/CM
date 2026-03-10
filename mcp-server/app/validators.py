"""Parameter validators for cloud operations."""

ALLOWED_INSTANCE_TYPES = {
    "t2.micro",
    "t2.small",
    "t2.medium",
    "t3.micro",
    "t3.small",
    "t3.medium",
}

ALLOWED_REGIONS = {
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-central-1",
    "ap-south-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "sa-east-1",
    "ca-central-1",
}


class ValidationError(Exception):
    pass


def validate_bucket_name(name: str) -> None:
    if not name or len(name) < 3 or len(name) > 63:
        raise ValidationError("Bucket name must be 3-63 characters")
    if not name[0].isalnum():
        raise ValidationError("Bucket name must start with a letter or number")
    import re
    if not re.match(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$", name):
        raise ValidationError(
            "Bucket name can only contain lowercase letters, numbers, hyphens, and dots"
        )


def validate_region(region: str) -> None:
    if region not in ALLOWED_REGIONS:
        raise ValidationError(
            f"Region '{region}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_REGIONS))}"
        )


def validate_instance_type(instance_type: str) -> None:
    if instance_type not in ALLOWED_INSTANCE_TYPES:
        raise ValidationError(
            f"Instance type '{instance_type}' is not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_INSTANCE_TYPES))}"
        )

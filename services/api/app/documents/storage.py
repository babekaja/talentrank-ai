"""Private MinIO access. A test implementation can replace get_storage in dependency overrides."""
from app.core.config import get_settings


class PrivateStorage:
    def __init__(self):
        from minio import Minio
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.client = Minio(settings.s3_endpoint, access_key=settings.s3_access_key,
                            secret_key=settings.s3_secret_key, secure=settings.s3_secure)

    def ensure_bucket(self):
        # No public bucket policies are ever applied.
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key: str, path: str, size: int, mime: str):
        with open(path, 'rb') as source:
            self.client.put_object(self.bucket, key, source, length=size, content_type=mime)

    def get(self, key: str):
        return self.client.get_object(self.bucket, key)

    def delete(self, key: str):
        self.client.remove_object(self.bucket, key)

    def purge(self, key: str):
        """Erase the exact object including old S3 versions and delete markers.

        A current-version delete alone does NOT erase personal data from a
        versioned MinIO bucket. Fail closed if the listing cannot be checked.
        This method is for privacy erasure, not routine upload rollback.
        """
        versions = [item for item in self.client.list_objects(
            self.bucket, prefix=key, recursive=True, include_version=True)
            if item.object_name == key]
        if not versions:
            # Already absent. On versioned buckets an unconditional DELETE could
            # CREATE a new delete marker, so do not issue it.
            return
        for version in versions:
            version_id = getattr(version, 'version_id', None)
            if version_id:
                self.client.remove_object(self.bucket, key, version_id=version_id)
            else:
                self.client.remove_object(self.bucket, key)
        remaining = [item for item in self.client.list_objects(
            self.bucket, prefix=key, recursive=True, include_version=True)
            if item.object_name == key]
        if remaining:
            raise RuntimeError('MinIO historical versions still contain personal data')


def get_storage() -> PrivateStorage:
    return PrivateStorage()

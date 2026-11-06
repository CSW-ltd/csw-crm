import io
from typing import Protocol

from app.core.config import Settings


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class MinioStorage:
    def __init__(self, s: Settings):
        from minio import Minio

        self.bucket = s.minio_bucket
        self.client = Minio(s.minio_endpoint, access_key=s.minio_access_key, secret_key=s.minio_secret_key,
                            secure=s.minio_secure, region=s.minio_region or None)
        self._ready = False

    def _ensure_bucket(self) -> None:
        if not self._ready:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
            self._ready = True

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._ensure_bucket()
        self.client.put_object(self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)

    def get(self, key: str) -> bytes:
        resp = self.client.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def delete(self, key: str) -> None:
        self._ensure_bucket()
        self.client.remove_object(self.bucket, key)


class MemoryStorage:
    """Testlar va lokal tajriba uchun."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get(self, key: str) -> bytes:
        return self.objects[key][0]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

"""Optional Cloudflare R2 storage for episode audio.

Keeping every mp3 in the git repo makes .git grow by hundreds of MB a month
(old files stay in history even after they're deleted). When the R2_* settings
are present, episode audio is uploaded to an R2 bucket instead and the feed
points at its public URL; the feed, transcripts and web player stay on GitHub
Pages. With the settings absent, everything behaves as before (mp3s are
written to docs/episodes and served from Pages).
"""
from . import config


def enabled() -> bool:
    return all(
        (
            config.R2_ACCOUNT_ID,
            config.R2_ACCESS_KEY_ID,
            config.R2_SECRET_ACCESS_KEY,
            config.R2_BUCKET,
            config.R2_PUBLIC_URL,
        )
    )


def _client():
    import boto3  # imported lazily so Pages-only setups don't need boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def public_url(key: str) -> str:
    return f"{config.R2_PUBLIC_URL}/{key}"


def owns_url(url: str) -> bool:
    return bool(config.R2_PUBLIC_URL) and url.startswith(config.R2_PUBLIC_URL + "/")


def upload_mp3(path, key: str) -> str:
    """Upload a local mp3 and return its public URL. Raises on failure."""
    _client().upload_file(
        str(path), config.R2_BUCKET, key, ExtraArgs={"ContentType": "audio/mpeg"}
    )
    return public_url(key)


def delete(key: str) -> None:
    _client().delete_object(Bucket=config.R2_BUCKET, Key=key)

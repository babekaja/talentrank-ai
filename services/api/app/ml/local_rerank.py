"""Explicit opt-in local-only ML adapters. Never fetch a model implicitly.

Load model files from a trusted, pre-provisioned directory; no APIs, hosted
inference, remote code or automatic installation in a recruitment request.
"""
from __future__ import annotations
from pathlib import Path


def _model_directory(path: str) -> str:
    location = Path(path).expanduser().resolve(strict=True)
    if not location.is_dir():
        raise ValueError('LOCAL_MODEL_DIRECTORY_REQUIRED')
    # No model names are accepted here, only actual directories already present.
    if not (location / 'config.json').exists() and not (location / 'modules.json').exists():
        raise ValueError('INVALID_LOCAL_MODEL_DIRECTORY')
    return str(location)


class LocalEmbeddingAdapter:
    def __init__(self, directory: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(_model_directory(directory),
                                         device='cpu', trust_remote_code=False,
                                         local_files_only=True)
    def encode(self, texts: list[str]):
        return self.model.encode(texts, batch_size=8, normalize_embeddings=True,
                                 show_progress_bar=False)


class LocalCrossEncoderAdapter:
    def __init__(self, directory: str):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(_model_directory(directory), device='cpu',
                                  trust_remote_code=False, local_files_only=True)
    def predict(self, pairs: list[tuple[str,str]]):
        # Raw scores are for ORDERING, never calibrated probabilities.
        return self.model.predict(pairs, batch_size=4, show_progress_bar=False)

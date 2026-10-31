"""Bounded streaming validation of user CVs and ZIP archives. No extracted archive paths."""
import hashlib
import io
import os
import tempfile
import zipfile
from pathlib import PurePosixPath
from fastapi import HTTPException, UploadFile
from app.core.config import get_settings

DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
PDF_MIME = 'application/pdf'


def clean_name(name: str) -> str:
    # Do not trust paths supplied by the client. Strip both Windows and Unix separators.
    name = name.replace('\\', '/').split('/')[-1]
    if not name or name in {'.', '..'} or '\x00' in name:
        raise HTTPException(422, 'Nom de fichier invalide')
    return name[:255]


def inspect_cv(path: str, name: str) -> str:
    suffix = os.path.splitext(name.lower())[1]
    with open(path, 'rb') as stream:
        header = stream.read(8)
    if suffix == '.pdf':
        if not header.startswith(b'%PDF-'):
            raise HTTPException(415, 'La signature du PDF ne correspond pas au format')
        return PDF_MIME
    if suffix == '.docx':
        try:
            with zipfile.ZipFile(path) as z:
                names = set(z.namelist())
                if '[Content_Types].xml' not in names or 'word/document.xml' not in names:
                    raise ValueError('Package DOCX incomplet')
                if len(names) > 2500 or sum(v.file_size for v in z.infolist()) > 30_000_000:
                    raise ValueError('DOCX trop complexe')
                if any(v.file_size > 100_000 and
                       (v.compress_size == 0 or v.file_size / v.compress_size > 200)
                       for v in z.infolist()):
                    raise ValueError('Compression DOCX suspecte')
                if any('vbaProject.bin' in n or n.endswith('.bin') for n in names):
                    raise ValueError('Fichier actif interdit')
        except (ValueError, zipfile.BadZipFile):
            raise HTTPException(415, 'DOCX invalide ou non autorisé') from None
        return DOCX_MIME
    raise HTTPException(415, 'Seuls PDF et DOCX sont acceptés')


async def spool_upload(upload: UploadFile, limit: int) -> tuple[str, int, str]:
    """Create bounded temporary file, returning path, byte length and SHA-256."""
    digest = hashlib.sha256()
    total = 0
    fd, path = tempfile.mkstemp(prefix='tr-cv-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise HTTPException(413, f'Document trop volumineux : limite de {limit // 1_000_000} Mo')
                digest.update(chunk)
                output.write(chunk)
        if total == 0:
            raise HTTPException(422, 'Fichier vide')
        return path, total, digest.hexdigest()
    except BaseException:
        os.unlink(path)
        raise


def validate_zip(path: str, max_files: int, max_file_size: int, max_total_size: int,
                 unsupported: list[str] | None = None):
    """Check complete archive before any ingestion; return CV entries only."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if not infos:
                raise HTTPException(422, 'Archive ZIP vide')
            # Allow a small number of folder/unsupported entries around the CVs.
            # Still cap the ZIP directory to avoid unbounded metadata processing.
            if len(infos) > max_files + 100:
                raise HTTPException(413, f'Archive ZIP : trop d’entrées (maximum {max_files + 100})')
            valid = []
            total = 0
            for info in infos:
                if info.is_dir():
                    continue
                name = info.filename.replace('\\', '/')
                p = PurePosixPath(name)
                if (p.is_absolute() or '..' in p.parts or name.startswith('./')
                    or ':' in name or '\x00' in name or info.flag_bits & 1
                    or (info.external_attr >> 16) & 0o170000 == 0o120000):
                    raise HTTPException(422, 'Chemin ou entrée ZIP interdits')
                if name.startswith('__MACOSX/') or name.split('/')[-1].startswith('.'):
                    continue
                if not name.lower().endswith(('.pdf', '.docx')):
                    if unsupported is None:
                        raise HTTPException(415, 'Le ZIP contient un format non autorisé')
                    unsupported.append(clean_name(name))
                    continue
                if info.file_size <= 0 or info.file_size > max_file_size:
                    raise HTTPException(413, f'Un fichier de l’archive dépasse la limite de {max_file_size // 1_000_000} Mo')
                if info.compress_size == 0 or info.file_size / info.compress_size > 100:
                    raise HTTPException(413, f'Taux de compression ZIP excessif pour {clean_name(info.filename)}')
                total += info.file_size
                if total > max_total_size:
                    raise HTTPException(413, 'Archive décompressée trop volumineuse')
                valid.append(info)
            if len(valid) > max_files or not valid:
                raise HTTPException(413, 'Archive vide ou trop de CV')
            if len({x.filename.lower() for x in valid}) != len(valid):
                raise HTTPException(409, 'Noms de fichiers dupliqués dans le ZIP')
            return valid
    except zipfile.BadZipFile:
        raise HTTPException(415, 'Archive ZIP corrompue') from None


def spool_zip_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int):
    fd, path = tempfile.mkstemp(prefix='tr-cv-', suffix='.tmp')
    digest = hashlib.sha256()
    count = 0
    try:
        with os.fdopen(fd, 'wb') as out, archive.open(info, 'r') as source:
            while part := source.read(1024 * 1024):
                count += len(part)
                if count > limit:
                    raise HTTPException(413, f'Décompression supérieure à la limite de {limit // 1_000_000} Mo')
                digest.update(part)
                out.write(part)
        return path, count, digest.hexdigest()
    except BaseException:
        os.unlink(path)
        raise

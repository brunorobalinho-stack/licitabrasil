"""Download de documentos com SHA256 dedup."""

import hashlib
import re
from pathlib import Path

from loguru import logger

from .config import Settings
from .storage import Database


class DocumentDownloader:
    """Baixa documentos com dedup por SHA256."""

    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db
        self.docs_dir = settings.docs_dir
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    async def download_pending(self, client, limit: int = 0) -> tuple[int, int, int]:
        """Baixa todos os documentos pendentes.

        Returns: (downloaded, skipped_dedup, failed)
        """
        pending = self.db.get_pending_downloads()
        if not pending:
            logger.info("No pending documents to download")
            return (0, 0, 0)

        if limit > 0:
            pending = pending[:limit]

        logger.info(f"Downloading {len(pending)} pending documents...")
        downloaded = 0
        skipped = 0
        failed = 0

        for doc in pending:
            url = doc["arquivo"]
            if not url:
                continue

            try:
                content = await client.fetch_document(url)
                if content is None:
                    failed += 1
                    continue

                sha = hashlib.sha256(content).hexdigest()

                # Check if we already have this exact file
                existing = self.db.doc_exists_by_hash(sha)
                if existing:
                    self.db.update_document_hash(doc["id"], sha, existing)
                    skipped += 1
                    continue

                # Save to disk
                local_path = self._save_file(doc, content, sha)
                self.db.update_document_hash(doc["id"], sha, str(local_path))
                downloaded += 1

                if (downloaded + skipped) % 50 == 0:
                    logger.info(f"Progress: {downloaded} downloaded, {skipped} dedup, {failed} failed")

            except Exception as e:
                logger.warning(f"Failed to download doc {doc['id']} ({url}): {e}")
                failed += 1

        logger.info(f"Download complete: {downloaded} new, {skipped} dedup, {failed} failed")
        return (downloaded, skipped, failed)

    def _save_file(self, doc: dict, content: bytes, sha: str) -> Path:
        """Salva arquivo em disco com nome organizado."""
        # Organize by licitacao_id
        lic_dir = self.docs_dir / str(doc["licitacao_id"])
        lic_dir.mkdir(parents=True, exist_ok=True)

        # Extract filename from URL or generate one
        filename = self._extract_filename(doc["arquivo"], doc["tipo"], sha)
        filepath = lic_dir / filename

        # Handle name collision
        if filepath.exists():
            filepath = lic_dir / f"{sha[:8]}_{filename}"

        filepath.write_bytes(content)
        return filepath

    @staticmethod
    def _extract_filename(url: str, tipo: str, sha: str) -> str:
        """Extrai nome do arquivo da URL ou gera um."""
        # Try to get filename from URL path
        parts = url.rstrip("/").split("/")
        if parts:
            last = parts[-1]
            if "." in last and len(last) < 200:
                # Clean up the filename
                return re.sub(r'[<>:"|?*]', "_", last)

        # Generate from tipo + hash
        ext = ".pdf"  # most common
        safe_tipo = re.sub(r'[<>:"|?*\s/\\]', "_", tipo)[:50]
        return f"{safe_tipo}_{sha[:8]}{ext}"

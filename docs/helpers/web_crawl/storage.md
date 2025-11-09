# Web Crawl Storage Architecture

The crawler now persists two artefacts per page:

1. The extracted text saved to ``.txt`` files.
2. A JSON metadata document capturing crawl depth, hash, byte size, and crawl
   identifiers.

The metadata records enable downstream automation to detect duplicates, audit
runs, and replay crawls without reparsing text files. Metadata is appended to an
optional JSONL index when the :mod:`scripts.crawl_site` CLI is invoked with
``--storage-index``.

## Directory Layout

```
output/
├── about-23c9e1ac.txt
├── about-23c9e1ac.json
├── index-fd03b993.txt
├── index-fd03b993.json
└── metadata.jsonl
```

Each ``.json`` file mirrors the text filename and includes fields:

- ``url`` – canonical URL after redirects.
- ``content_type`` – response content type (when provided).
- ``content_hash`` – SHA-1 hash of the extracted text.
- ``fetched_at`` – Unix timestamp captured immediately after fetch.
- ``depth`` – crawl depth relative to the root URL.
- ``crawl_id`` – deterministic identifier derived from the root URL.
- ``text_bytes`` – size of the persisted text in bytes.

## Custom Storage Backends

The new :class:`helpers.web_crawl.storage.StorageBackend` protocol allows
plugging in alternative persistence layers (databases, cloud storage, etc.).
When constructing :class:`helpers.web_crawl.crawler.Crawler` you can pass a
custom backend via the ``storage`` keyword argument. Provide either
``storage`` *or* ``storage_dir`` – never both.

```python
from helpers.web_crawl import Crawler, StorageBackend, StorageDocument

class MemoryStorage(StorageBackend):
    def __init__(self) -> None:
        self.documents: list[StorageDocument] = []

    def persist(self, document: StorageDocument) -> None:
        self.documents.append(document)
        return None

    def close(self) -> None:
        pass

crawler = Crawler("https://example.com", storage=MemoryStorage())
```

Remember to call ``close()`` on custom backends if they maintain connections or
file handles.

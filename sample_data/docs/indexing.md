# Building and Updating the Index

## Crawling a website
To index a public documentation site, set `KB_BASE_URL` and `KB_ROOT_URL` in `.env`, then run `./scripts/sync_kb.sh`. The script discovers article URLs from the sitemap and from the pages under the root URL, downloads the HTML, extracts clean text, splits it into chunks and builds a FAISS vector index. If your site uses different URL segments for article and listing pages, set `KB_ARTICLE_SEGMENT` and `KB_LISTING_SEGMENT`.

## Indexing your own files
You do not need a website. Put Markdown files in a folder and run `python scripts/build_sample_corpus.py --docs-dir your_docs --out data/clean/articles.jsonl`, then run `python indexer/build_index.py --articles data/clean/articles.jsonl --out-dir data/index`. Each file becomes one article, and its first heading becomes the title.

## Chunking
Articles are split at headings and then into chunks of about 550 words with an overlap of 100 words. Smaller chunks give more precise citations; larger chunks keep more context together. Change them with `--chunk-tokens` and `--overlap-tokens`.

## Scheduling updates
Run `./scripts/sync_kb.sh` from cron to refresh the index periodically. Restart the API after the index is rebuilt so that the new files are loaded.

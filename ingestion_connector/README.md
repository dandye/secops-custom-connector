# SecOps Investigations Ingestion Connector

Harvests **SecOps Investigations** via **SecOps OneMCP** (`list_investigations`), converts them into `discoveryengine.Document` objects, and ingests them into Google Cloud Discovery Engine Data Stores for grounded search and RAG.

## Files
- `secops_investigations_mcp.py`: OneMCP client for harvesting SecOps investigations.
- `connector.py`: Converts investigations to Discovery Engine Document protobufs & manages DataStores.
- `main.py`: CLI runner.

## Quick Usage
```bash
# Dry run:
python main.py --dry-run

# Inline ingestion:
python main.py --project-id YOUR_PROJECT_ID --data-store-id secops-inv-ds1 --mode inline
```

"""CLI Runner for SecOps Investigations Ingestion Connector.

Usage:
  # Offline dry-run test:
  python ingestion_connector/main.py --dry-run

  # Run live inline ingestion:
  python ingestion_connector/main.py --project-id MY_PROJECT_ID --data-store-id secops-inv-ds1 --mode inline

  # Run live GCS bulk ingestion:
  python ingestion_connector/main.py --project-id MY_PROJECT_ID --data-store-id secops-inv-ds1 \
    --mode gcs --gcs-bucket MY_BUCKET
"""

import argparse
import sys
import logging
from ingestion_connector.secops_investigations_mcp import SecOpsInvestigationsMCPClient
from ingestion_connector.connector import (
    harvest_and_convert_investigations,
    get_or_create_ims_data_store,
    load_ims_data,
    get_or_create_data_store,
    upload_documents_inline,
    convert_documents_to_jsonl,
    upload_jsonl_to_gcs,
    import_documents_from_gcs,
)
from google.cloud import discoveryengine_v1 as discoveryengine
from google.api_core import exceptions as gcp_exceptions

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_dry_run(client: SecOpsInvestigationsMCPClient):
    """Executes offline dry-run test for SecOps Investigations harvesting & conversion."""
    logger.info("=== RUNNING INGESTION CONNECTOR DRY-RUN MODE ===")
    docs = harvest_and_convert_investigations(client)
    jsonl_output = convert_documents_to_jsonl(docs)

    print("\n--- Summary ---")
    print(f"Harvested and converted {len(docs)} SecOps Investigations into Discovery Engine documents.\n")
    print("--- Sample Converted Document JSON ---")
    if docs:
        print(discoveryengine.Document.to_json(docs[0], indent=2))
        print("\n--- Converted JSONL Payload (First 300 chars) ---")
        print(jsonl_output[:300] + "...\n")
    print("Ingestion Connector dry-run completed successfully!")


def main():
    parser = argparse.ArgumentParser(description="SecOps Investigations Ingestion Connector")

    # SecOps OneMCP options
    parser.add_argument("--secops-mcp-url", default="https://us-chronicle.googleapis.com/mcp", help="SecOps OneMCP endpoint")
    parser.add_argument("--secops-project-id", default="", help="SecOps GCP Project ID")
    parser.add_argument("--secops-customer-id", default="", help="SecOps Customer ID")
    parser.add_argument("--secops-region", default="us", help="SecOps Region")

    # Discovery Engine options
    parser.add_argument("--project-id", default="ucs-3p-connectors-testing", help="GCP Project ID for Discovery Engine")
    parser.add_argument("--location", default="global", help="GCP Location")
    parser.add_argument("--ims-id", default="secops-inv-ims1", help="Identity Mapping Store ID")
    parser.add_argument("--data-store-id", default="secops-inv-ds1", help="Data Store ID")
    parser.add_argument("--data-store-display-name", default="secops-investigations-datastore", help="Data Store Display Name")
    parser.add_argument("--branch-id", default="0", help="Data Store Branch ID")
    parser.add_argument("--mode", choices=["inline", "gcs"], default="inline", help="Ingestion mode (inline or gcs)")
    parser.add_argument("--gcs-bucket", help="Google Cloud Storage Bucket Name (required for --mode gcs)")
    parser.add_argument("--gcs-blob-path", default="secops/investigations.jsonl", help="Blob path inside GCS bucket")
    parser.add_argument("--dry-run", action="store_true", help="Perform offline dry-run test without calling GCP APIs")

    args = parser.parse_args()

    client = SecOpsInvestigationsMCPClient(
        endpoint_url=args.secops_mcp_url,
        project_id=args.secops_project_id,
        customer_id=args.secops_customer_id,
        region=args.secops_region,
    )

    if args.dry_run:
        run_dry_run(client)
        return

    logger.info(f"Starting SecOps Investigations Ingestion Connector (Mode: {args.mode})...")

    # Step 1: Harvest investigations and convert to Discovery Engine documents
    docs = harvest_and_convert_investigations(client)
    print(f"Converted {len(docs)} Document messages for SecOps Investigations.")

    try:
        # Step 2: Get or create Identity Mapping Store
        logger.info("Step #1: Retrieve/Create Identity Mapping Store...")
        ims_store = get_or_create_ims_data_store(args.project_id, args.location, args.ims_id)
        print(f"IMS Store: {ims_store.name}")

        # Step 3: Load sample Identity Mappings
        logger.info("Step #2: Load Identity Mapping data...")
        sample_identity_mappings = [
            discoveryengine.IdentityMappingEntry(
                external_identity="secops_investigator_1",
                user_id="soc_analyst@company.com",
            ),
            discoveryengine.IdentityMappingEntry(
                external_identity="secops_ir_team",
                group_id="incident-response@company.com",
            ),
        ]
        ims_response = load_ims_data(ims_store, sample_identity_mappings)
        print(f"Loaded {len(sample_identity_mappings)} identity mapping entries successfully.")

        # Step 4: Create Data Store and bind Identity Mapping Store
        logger.info("Step #3: Create Data Store and bind IMS...")
        data_store = get_or_create_data_store(
            project_id=args.project_id,
            location=args.location,
            display_name=args.data_store_display_name,
            data_store_id=args.data_store_id,
            identity_mapping_store=ims_store.name,
        )
        print(f"Data Store Name: {data_store.name}")
        print(f"ACL Enabled: {data_store.acl_enabled}")
        print(f"Identity Mapping Store Bound: {data_store.identity_mapping_store}")

        # Step 5: Ingest Documents
        if args.mode == "inline":
            logger.info("Step #4: Uploading documents inline (Incremental Reconciliation)...")
            metadata = upload_documents_inline(
                args.project_id, args.location, args.data_store_id, args.branch_id, docs
            )
            print(f"Successfully uploaded {metadata.success_count} documents inline.")
        elif args.mode == "gcs":
            if not args.gcs_bucket:
                logger.error("--gcs-bucket argument is required when running in gcs mode.")
                sys.exit(1)
            logger.info("Step #4: Serializing documents to JSONL and uploading to GCS...")
            jsonl_payload = convert_documents_to_jsonl(docs)
            gcs_uri = upload_jsonl_to_gcs(jsonl_payload, args.gcs_bucket, args.gcs_blob_path)
            print(f"Uploaded JSONL to {gcs_uri}")

            logger.info("Step #5: Importing documents from GCS (Full Reconciliation)...")
            metadata = import_documents_from_gcs(
                args.project_id, args.location, args.data_store_id, args.branch_id, gcs_uri
            )
            print(f"Successfully imported {metadata.success_count} documents from GCS.")

    except gcp_exceptions.GoogleAPICallError as e:
        print("\n--- API Call Failed ---")
        print(f"Server Error Message: {e.message}")
        print(f"Status Code: {e.code}")
    except Exception as e:
        print(f"\nAn error occurred during execution: {e}")


if __name__ == "__main__":
    main()

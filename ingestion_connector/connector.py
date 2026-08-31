"""Ingestion Connector for SecOps Investigations.

Harvests SecOps Investigations via SecOps OneMCP, converts them into Discovery Engine
Document messages, binds Identity Mapping Stores, and ingests them into Discovery Engine.
"""

from typing import List, Dict, Any, Optional
import json
import logging

from google.api_core import exceptions as gcp_exceptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage

from .secops_investigations_mcp import SecOpsInvestigationsMCPClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def convert_investigations_to_documents(investigations: List[Dict[str, Any]]) -> List[discoveryengine.Document]:
    """Convert SecOps Investigation records into Discovery Engine Document messages."""
    docs: List[discoveryengine.Document] = []
    for inv in investigations:
        title = inv.get("displayName") or f"SecOps Investigation {inv.get('id')}"
        entities_str = ", ".join(inv.get("entities", []))
        body = (
            f"Summary: {inv.get('description', '')}\n"
            f"Verdict: {inv.get('verdict', '')} (Confidence: {inv.get('confidenceScore', 0.0) * 100:.1f}%)\n"
            f"Status: {inv.get('status', '')} | Assignee: {inv.get('assignee', '')}\n"
            f"Involved Entities: {entities_str}"
        )
        payload = {
            "title": title,
            "body": body,
            "url": inv.get("url", f"https://chronicle.security/investigations/{inv.get('id')}"),
            "verdict": inv.get("verdict"),
            "confidence_score": inv.get("confidenceScore"),
            "status": inv.get("status"),
            "assignee": inv.get("assignee"),
            "entities": inv.get("entities", []),
            "created_time": inv.get("createdTime"),
            "updated_time": inv.get("updatedTime"),
            "type": "secops_investigation",
        }
        doc = discoveryengine.Document(
            id=str(inv.get("id", f"inv_{len(docs)+1}")),
            json_data=json.dumps(payload),
        )
        docs.append(doc)
    return docs


def harvest_and_convert_investigations(client: SecOpsInvestigationsMCPClient) -> List[discoveryengine.Document]:
    """Harvests investigations via SecOps OneMCP and converts them to Discovery Engine documents."""
    investigations = client.fetch_investigations()
    logger.info(f"Harvested {len(investigations)} SecOps Investigations.")
    return convert_investigations_to_documents(investigations)


def get_or_create_ims_data_store(
    project_id: str,
    location: str,
    identity_mapping_store_id: str,
) -> discoveryengine.DataStore:
    """Get or create an Identity Mapping Store (IMS)."""
    client_ims = discoveryengine.IdentityMappingStoreServiceClient()
    parent_ims = client_ims.location_path(project=project_id, location=location)
    name = f"projects/{project_id}/locations/{location}/identityMappingStores/{identity_mapping_store_id}"

    try:
        request = discoveryengine.GetIdentityMappingStoreRequest(name=name)
        logger.info(f"Retrieving existing Identity Mapping Store: {name}")
        return client_ims.get_identity_mapping_store(request=request)
    except Exception as e:
        logger.info(f"Creating new Identity Mapping Store '{identity_mapping_store_id}' ({e})...")
        identity_mapping_store = discoveryengine.IdentityMappingStore()
        request = discoveryengine.CreateIdentityMappingStoreRequest(
            parent=parent_ims,
            identity_mapping_store=identity_mapping_store,
            identity_mapping_store_id=identity_mapping_store_id,
        )
        return client_ims.create_identity_mapping_store(request=request)


def load_ims_data(
    ims_store: discoveryengine.DataStore,
    id_mapping_data: List[discoveryengine.IdentityMappingEntry],
) -> Optional[discoveryengine.DataStore]:
    """Ingest identity mapping entries into identity store."""
    client_ims = discoveryengine.IdentityMappingStoreServiceClient()
    inline_source = discoveryengine.ImportIdentityMappingsRequest.InlineSource(
        identity_mapping_entries=id_mapping_data
    )
    request_ims = discoveryengine.ImportIdentityMappingsRequest(
        identity_mapping_store=ims_store.name,
        inline_source=inline_source,
    )

    try:
        logger.info("Importing identity mappings into IMS store...")
        operation = client_ims.import_identity_mappings(request=request_ims)
        result = operation.result()
        return result
    except Exception as e:
        logger.error(f"IMS Load Error: {e}")
        return None


def get_or_create_data_store(
    project_id: str,
    location: str,
    display_name: str,
    data_store_id: str,
    identity_mapping_store: str,
) -> discoveryengine.DataStore:
    """Get or create a Discovery Engine DataStore bound to an Identity Mapping Store."""
    client = discoveryengine.DataStoreServiceClient()
    ds_name = client.data_store_path(project_id, location, data_store_id)

    try:
        logger.info(f"Retrieving existing DataStore: {ds_name}")
        result = client.get_data_store(request={"name": ds_name})
        return result
    except Exception as e:
        logger.info(f"Creating new DataStore '{data_store_id}' ({e})...")
        parent = client.collection_path(project_id, location, "default_collection")
        operation = client.create_data_store(
            request={
                "parent": parent,
                "data_store": discoveryengine.DataStore(
                    display_name=display_name,
                    acl_enabled=True,
                    industry_vertical=discoveryengine.IndustryVertical.GENERIC,
                    identity_mapping_store=identity_mapping_store,
                ),
                "data_store_id": data_store_id,
            }
        )
        result = operation.result()
        return result


def upload_documents_inline(
    project_id: str,
    location: str,
    data_store_id: str,
    branch_id: str,
    documents: List[discoveryengine.Document],
) -> discoveryengine.ImportDocumentsMetadata:
    """Import Document messages inline (Incremental Reconciliation)."""
    client = discoveryengine.DocumentServiceClient()
    parent = client.branch_path(
        project=project_id,
        location=location,
        data_store=data_store_id,
        branch=branch_id,
    )
    request = discoveryengine.ImportDocumentsRequest(
        parent=parent,
        inline_source=discoveryengine.ImportDocumentsRequest.InlineSource(
            documents=documents,
        ),
    )
    logger.info(f"Uploading {len(documents)} documents inline to branch '{branch_id}'...")
    operation = client.import_documents(request=request)
    operation.result()
    return operation.metadata


def convert_documents_to_jsonl(documents: List[discoveryengine.Document]) -> str:
    """Serialize Document messages to JSONL format."""
    return "\n".join(
        discoveryengine.Document.to_json(doc, indent=None)
        for doc in documents
    ) + "\n"


def upload_jsonl_to_gcs(jsonl: str, bucket_name: str, blob_name: str) -> str:
    """Upload JSONL string content to GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    logger.info(f"Uploading JSONL payload to gs://{bucket_name}/{blob_name}...")
    blob.upload_from_string(jsonl, content_type="application/json")
    return f"gs://{bucket_name}/{blob_name}"


def import_documents_from_gcs(
    project_id: str,
    location: str,
    data_store_id: str,
    branch_id: str,
    gcs_uri: str,
) -> discoveryengine.ImportDocumentsMetadata:
    """Bulk-import documents from GCS using FULL reconciliation mode."""
    client = discoveryengine.DocumentServiceClient()
    parent = client.branch_path(
        project=project_id,
        location=location,
        data_store=data_store_id,
        branch=branch_id,
    )
    gcs_source = discoveryengine.GcsSource(input_uris=[gcs_uri])
    request = discoveryengine.ImportDocumentsRequest(
        parent=parent,
        gcs_source=gcs_source,
        reconciliation_mode=discoveryengine.ImportDocumentsRequest.ReconciliationMode.FULL,
    )
    logger.info(f"Importing documents from {gcs_uri} with FULL reconciliation mode...")
    operation = client.import_documents(request=request)
    operation.result()
    return operation.metadata

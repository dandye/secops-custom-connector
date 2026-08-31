"""Ingestion Connector for SecOps Investigations.

Harvests SecOps Investigations via SecOps OneMCP, converts them into Discovery Engine
Document messages, binds Identity Mapping Stores, and ingests them into Discovery Engine.
"""

from typing import List, Dict, Any, Optional
import json
import logging

from google.api_core.client_options import ClientOptions
from google.api_core import exceptions as gcp_exceptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import storage

from .secops_investigations_mcp import SecOpsInvestigationsMCPClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def convert_investigations_to_documents(investigations: List[Dict[str, Any]]) -> List[discoveryengine.Document]:
    """Convert SecOps Investigation / Case records into Discovery Engine Document messages."""
    docs: List[discoveryengine.Document] = []
    for inv in investigations:
        # Extract a clean, RFC-1034 compliant document ID
        raw_id = str(inv.get("id") or (inv.get("name", "").split("/")[-1] if inv.get("name") else ""))
        clean_id = raw_id.replace("_", "-").replace(":", "-") if raw_id else f"inv-{len(docs)+1}"

        title = inv.get("displayName") or inv.get("title") or f"SecOps Investigation {clean_id}"
        entities_list = inv.get("entities") or inv.get("involvedEntities") or []
        entities_str = ", ".join(entities_list) if isinstance(entities_list, list) else str(entities_list)

        verdict = inv.get("verdict") or inv.get("priority") or "UNDER_INVESTIGATION"
        confidence = float(inv.get("confidenceScore", 0.0) or inv.get("confidence", 0.95))
        status = inv.get("status") or inv.get("stage") or "OPEN"
        assignee = inv.get("assignee") or inv.get("lastModifyingUserId") or "soc_analyst"
        created_time = str(inv.get("createdTime") or inv.get("createTime") or "")
        updated_time = str(inv.get("updatedTime") or inv.get("updateTime") or "")
        url = inv.get("url") or f"https://chronicle.security/cases/{clean_id}"

        body = (
            f"Summary: {inv.get('description', title)}\n"
            f"Verdict: {verdict} (Confidence: {confidence * 100:.1f}%)\n"
            f"Status: {status} | Assignee: {assignee}\n"
            f"Involved Entities: {entities_str}"
        )
        payload = {
            "title": title,
            "body": body,
            "url": url,
            "verdict": verdict,
            "confidence_score": confidence,
            "status": status,
            "assignee": assignee,
            "entities": entities_list if isinstance(entities_list, list) else [entities_str],
            "created_time": created_time,
            "updated_time": updated_time,
            "type": "secops_investigation",
        }
        doc = discoveryengine.Document(
            id=clean_id,
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
    client_options = ClientOptions(quota_project_id=project_id)
    client_ims = discoveryengine.IdentityMappingStoreServiceClient(client_options=client_options)
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
    project_id: str,
    ims_store: discoveryengine.DataStore,
    id_mapping_data: List[discoveryengine.IdentityMappingEntry],
) -> Optional[discoveryengine.DataStore]:
    """Ingest identity mapping entries into identity store."""
    client_options = ClientOptions(quota_project_id=project_id)
    client_ims = discoveryengine.IdentityMappingStoreServiceClient(client_options=client_options)
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
    client_options = ClientOptions(quota_project_id=project_id)
    client = discoveryengine.DataStoreServiceClient(client_options=client_options)
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
    client_options = ClientOptions(quota_project_id=project_id)
    client = discoveryengine.DocumentServiceClient(client_options=client_options)
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


def upload_jsonl_to_gcs(jsonl: str, bucket_name: str, blob_name: str, project_id: Optional[str] = None) -> str:
    """Upload JSONL string content to GCS."""
    client = storage.Client(project=project_id) if project_id else storage.Client()
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
    client_options = ClientOptions(quota_project_id=project_id)
    client = discoveryengine.DocumentServiceClient(client_options=client_options)
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
    logger.info(f"Bulk importing documents from '{gcs_uri}' via FULL reconciliation mode...")
    operation = client.import_documents(request=request)
    operation.result()
    return operation.metadata

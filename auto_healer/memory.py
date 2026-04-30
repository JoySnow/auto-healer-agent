"""
ChromaDB Long-Term Memory (RAG) Implementation

This module implements the memory layer using ChromaDB for storing and retrieving
past incident Root Cause Analysis (RCA) reports. The agent uses this to recall
similar historical incidents before debugging, implementing the RAG pattern.

Key Functions:
- initialize_chromadb(): Setup ChromaDB collection
- query_past_incidents(): Semantic search for similar incidents (RAG recall)
- save_incident(): Store approved RCA reports to memory
"""
from typing import Dict, List, Optional
import logging
from datetime import datetime
import json

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("ChromaDB not installed. Memory features will be disabled.")

logger = logging.getLogger(__name__)

# Global ChromaDB client and collection (initialized once)
_chroma_client: Optional[chromadb.Client] = None
_collection: Optional[chromadb.Collection] = None

COLLECTION_NAME = "incident_history"
PERSIST_DIRECTORY = ".chromadb"


def initialize_chromadb() -> bool:
    """
    Initialize ChromaDB client and create/load the incident_history collection.

    This should be called once at application startup. It creates a persistent
    ChromaDB instance in the .chromadb/ directory.

    Returns:
        bool: True if initialization successful, False otherwise.

    Example:
        >>> initialize_chromadb()
        True
        >>> # ChromaDB is now ready for queries
    """
    global _chroma_client, _collection

    if not CHROMADB_AVAILABLE:
        logger.error("ChromaDB not installed. Cannot initialize memory.")
        return False

    try:
        # Initialize ChromaDB client with persistence
        _chroma_client = chromadb.Client(Settings(
            persist_directory=PERSIST_DIRECTORY,
            anonymized_telemetry=False
        ))

        # Get or create collection
        # Note: ChromaDB will use default embedding function if not specified
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Historical incident RCA reports for auto-healer agent"}
        )

        incident_count = _collection.count()
        logger.info(f"ChromaDB initialized successfully. Collection '{COLLECTION_NAME}' has {incident_count} incidents.")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB: {str(e)}")
        return False


def query_past_incidents(alert_info: Dict, top_k: int = 3) -> str:
    """
    Query ChromaDB for similar past incidents using semantic search (RAG).

    This function takes the current alert information and searches the vector database
    for historically similar incidents. It returns a formatted string with the most
    relevant past RCA reports to provide context to the agents.

    Args:
        alert_info (dict): Current incident metadata.
                          Must contain: "service", "status_code"
                          Optional: "error_message", "chaos_type"
        top_k (int): Number of similar incidents to retrieve. Default is 3.

    Returns:
        str: Formatted string containing similar past incidents, or empty string if none found.
             Format:
             "Similar past incidents:
              1) [2024-03-15] order-service 500 - Root cause: ZeroDivisionError in payment calculation
              2) [2024-03-10] order-service 502 - Root cause: Payment gateway timeout
              ..."

    Example:
        >>> alert = {"service": "order-service", "status_code": 500}
        >>> context = query_past_incidents(alert, top_k=3)
        >>> print(context)
        Similar past incidents:
        1) [2024-03-15] order-service 500 - Root cause: ...
    """
    global _collection

    if _collection is None:
        logger.warning("ChromaDB not initialized. Call initialize_chromadb() first.")
        return ""

    try:
        # Build query string for semantic search
        service = alert_info.get("service", "unknown")
        status_code = alert_info.get("status_code", 0)
        error_msg = alert_info.get("error_message", "")

        query_text = f"Service: {service}, Status: {status_code}, Error: {error_msg}"

        # Query ChromaDB for similar incidents
        results = _collection.query(
            query_texts=[query_text],
            n_results=min(top_k, _collection.count())  # Don't query more than available
        )

        # Check if any results found
        if not results['documents'] or not results['documents'][0]:
            logger.info("No similar past incidents found in memory.")
            return ""

        # Format results
        incidents = []
        for idx, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0]), 1):
            timestamp = metadata.get('timestamp', 'unknown date')
            service_name = metadata.get('service', 'unknown service')
            status = metadata.get('status_code', 'unknown')

            # Truncate RCA if too long (keep first 200 chars)
            rca_summary = doc[:200] + "..." if len(doc) > 200 else doc

            incidents.append(
                f"{idx}) [{timestamp}] {service_name} {status} - {rca_summary}"
            )

        formatted_context = "Similar past incidents:\n" + "\n".join(incidents)

        logger.info(f"Found {len(incidents)} similar past incidents for {service} {status_code}")

        return formatted_context

    except Exception as e:
        logger.error(f"Error querying past incidents: {str(e)}")
        return ""


def save_incident(rca_report: str, alert_info: Dict) -> bool:
    """
    Save a human-approved RCA report to ChromaDB for future reference.

    This function should only be called AFTER the Human-in-the-Loop (HITL) node
    approves the RCA report. It embeds the report and stores it with metadata
    for future semantic search.

    Args:
        rca_report (str): The complete Root Cause Analysis report generated by agents.
        alert_info (dict): Incident metadata (service, status_code, timestamp, etc.)

    Returns:
        bool: True if save successful, False otherwise.

    Example:
        >>> alert = {"service": "order-service", "status_code": 500, "timestamp": "2024-04-30T10:30:00Z"}
        >>> rca = "Root Cause: ZeroDivisionError in line 42 of order/app.py..."
        >>> save_incident(rca, alert)
        True
    """
    global _collection

    if _collection is None:
        logger.error("ChromaDB not initialized. Call initialize_chromadb() first.")
        return False

    try:
        # Generate unique ID for this incident
        incident_id = f"{alert_info.get('service', 'unknown')}_{alert_info.get('timestamp', datetime.utcnow().isoformat())}"

        # Extract metadata
        metadata = {
            "service": alert_info.get("service", "unknown"),
            "status_code": alert_info.get("status_code", 0),
            "timestamp": alert_info.get("timestamp", datetime.utcnow().isoformat()),
            "chaos_type": alert_info.get("chaos_type", "none")
        }

        # Add to ChromaDB
        _collection.add(
            ids=[incident_id],
            documents=[rca_report],
            metadatas=[metadata]
        )

        logger.info(f"Successfully saved incident to memory: {incident_id}")

        return True

    except Exception as e:
        logger.error(f"Failed to save incident to memory: {str(e)}")
        return False


def get_memory_stats() -> Dict:
    """
    Get statistics about the memory database.

    Returns:
        dict: Memory statistics including total incidents, collection info.
    """
    global _collection

    if _collection is None:
        return {"error": "ChromaDB not initialized"}

    try:
        count = _collection.count()
        return {
            "collection_name": COLLECTION_NAME,
            "total_incidents": count,
            "persist_directory": PERSIST_DIRECTORY
        }
    except Exception as e:
        logger.error(f"Error getting memory stats: {str(e)}")
        return {"error": str(e)}

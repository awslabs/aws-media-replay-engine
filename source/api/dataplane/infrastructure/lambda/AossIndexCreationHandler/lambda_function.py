import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# Environment variables
SUMMARY_SEARCH_COLLECTION = os.getenv(
    "SUMMARY_SEARCH_COLLECTION", "mre-summary-collection"
)
VECTORSEARCH_COLLECTION = os.getenv(
    "VECTORSEARCH_COLLECTION", "mre-vectorsearch-collection"
)
KNN_INDEX_NAME = os.getenv("KNN_INDEX_NAME", "mre-knn-index")
EVENT_INDEX_NAME = os.getenv("EVENT_INDEX_NAME", "mre-event-summary-index")
PROGRAM_INDEX_NAME = os.getenv("PROGRAM_INDEX_NAME", "mre-program-summary-index")
REGION = os.getenv("OPENSEARCH_REGION", "us-east-1")

# AWS clients and authentication
credentials = boto3.Session().get_credentials()
aoss_client = boto3.client("opensearchserverless", region_name=REGION)
HTTP_AUTH = AWSV4SignerAuth(credentials, REGION, "aoss")


def opensearch_client(aoss_endpoint):
    return OpenSearch(
        hosts=[{"host": aoss_endpoint.replace("https://", "", 1), "port": 443}],
        http_auth=HTTP_AUTH,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
    )


def handler(event, context):
    print(event)
    request_type = event.get("RequestType")

    if request_type == "Create" or request_type == "Update":
        return create_indexes()
    elif request_type == "Delete":
        return on_delete()
    else:
        raise ValueError(f"Unknown request type: {request_type}")


def check_opensearch_index(client, index_name):
    try:
        return client.indices.exists(index=index_name)
    except Exception as e:
        print(f"Error checking index {index_name}: {e}")
        raise


def get_opensearch_endpoint(collection_name):
    try:
        response = aoss_client.batch_get_collection(names=[collection_name])

        if not response["collectionDetails"]:
            raise ValueError(f"Collection {collection_name} not found")

        return response["collectionDetails"][0]["collectionEndpoint"]
    except Exception as e:
        print(f"Error getting endpoint for collection {collection_name}: {e}")
        raise


def get_knn_index_map():
    return {
        "settings": {
            "index": {"knn": "true", "number_of_shards": 2, "number_of_replicas": 0}
        },
        "mappings": {
            "properties": {
                "End": {"type": "text"},
                "Event": {"type": "text"},
                "PluginName": {"type": "text"},
                "Program": {"type": "text"},
                "Start": {"type": "text"},
                "content": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "engine": "faiss",
                        "space_type": "innerproduct",
                        "name": "hnsw",
                        "parameters": {},
                    },
                },
            }
        },
    }


def create_summary_index():
    try:
        summary_aoss_endpoint = get_opensearch_endpoint(SUMMARY_SEARCH_COLLECTION)
        summary_client = opensearch_client(summary_aoss_endpoint)

        index_settings = {
            "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 1}}
        }

        if check_opensearch_index(summary_client, EVENT_INDEX_NAME):
            print(
                f"Index {EVENT_INDEX_NAME} already exists in collection {SUMMARY_SEARCH_COLLECTION}"
            )
        else:
            event_response = summary_client.indices.create(
                index=EVENT_INDEX_NAME, body=index_settings
            )

        if check_opensearch_index(summary_client, PROGRAM_INDEX_NAME):
            print(
                f"Index {PROGRAM_INDEX_NAME} already exists in collection {SUMMARY_SEARCH_COLLECTION}"
            )
        else:
            program_reponse = summary_client.indices.create(
                index=PROGRAM_INDEX_NAME, body=index_settings
            )

        return {
            "Status": "SUCCESS",
            "Reason": "Indexes created successfully",
            "PhysicalResourceId": "index_creation_function",
            "Data": {"ProgramIndex": program_reponse, "EventIndex": event_response},
        }
    except Exception as e:
        print(f"Error creating index in collection {SUMMARY_SEARCH_COLLECTION}: {e}")
        raise


def create_vectorsearch_index():
    try:
        vectorsearch_aoss_endpoint = get_opensearch_endpoint(VECTORSEARCH_COLLECTION)
        vectorsearch_client = opensearch_client(vectorsearch_aoss_endpoint)

        if check_opensearch_index(vectorsearch_client, KNN_INDEX_NAME):
            return f"Index {KNN_INDEX_NAME} already exists in collection {VECTORSEARCH_COLLECTION}"

        response = vectorsearch_client.indices.create(
            index=KNN_INDEX_NAME, body=get_knn_index_map()
        )
        print(
            f"Created index {KNN_INDEX_NAME} in collection {VECTORSEARCH_COLLECTION}: {response}"
        )

        return response
    except Exception as e:
        print(
            f"Error creating index {KNN_INDEX_NAME} in collection {VECTORSEARCH_COLLECTION}: {e}"
        )
        raise


def create_indexes():
    try:
        summary_response = create_summary_index()
        vectorsearch_response = create_vectorsearch_index()

        return {
            "Status": "SUCCESS",
            "Reason": "Indexes created successfully",
            "PhysicalResourceId": "index_creation_function",
            "Data": {
                "SummaryResponse": summary_response,
                "VectorsearchResponse": vectorsearch_response,
            },
        }
    except Exception as e:
        print(f"Error creating indexes: {e}")
        raise


def on_delete():
    try:
        for collection in [SUMMARY_SEARCH_COLLECTION, VECTORSEARCH_COLLECTION]:
            response = aoss_client.list_collections(
                collectionFilters={"name": collection}
            )
            if not response["collectionSummaries"]:
                print(f"No collections found for {collection}")
                continue

            collection_id = response["collectionSummaries"][0]["id"]
            aoss_client.delete_collection(id=collection_id)
            print(f"Deleted collection {collection} with ID {collection_id}")

        return {
            "Status": "SUCCESS",
            "Reason": "AOSS Collections and Indexes deleted successfully",
            "PhysicalResourceId": "index_creation_function",
        }
    except Exception as e:
        print(f"Error deleting collection: {e}")
        raise

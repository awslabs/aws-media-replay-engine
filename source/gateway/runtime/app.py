import os
from chalice import IAMAuthorizer
from chalice import Chalice, AuthResponse
from chalice import ChaliceViewError, BadRequestError, NotFoundError, ConflictError
import requests
import boto3
from chalice import Response
import json
import jwt
from requests_aws4auth import AWS4Auth

app = Chalice(app_name="aws-mre-gateway-api")
authorizer = IAMAuthorizer()
session = boto3.session.Session()
sec_client = session.client(service_name="secretsmanager")
API_AUTH_SECRET_KEY_NAME = os.environ["API_AUTH_SECRET_KEY_NAME"]
MRE_JWT_ISSUER = os.environ["MRE_JWT_ISSUER"]

SERVICE_ROUTER = {
    "PluginUrl": os.environ["PLUGIN_URL"],
    "SystemUrl": os.environ["SYSTEM_URL"],
    "ProfileUrl": os.environ["PROFILE_URL"],
    "ModelUrl": os.environ["MODEL_URL"],
    "PromptCatalogUrl": os.getenv("PROMPT_CATALOG_URL", None),
    "EventUrl": os.environ["EVENT_URL"],
    "ContentGroupUrl": os.environ["CONTENT_GROUP_URL"],
    "ProgramUrl": os.environ["PROGRAM_URL"],
    "WorkflowUrl": os.environ["WORKFLOW_URL"],
    "ReplayUrl": os.environ["REPLAY_URL"],
    "CustomPrioritiesUrl": os.environ["CUSTOM_PRIORITIES_URL"],
}


def get_iam_auth():
    return AWS4Auth(
        os.environ["AWS_ACCESS_KEY_ID"],
        os.environ["AWS_SECRET_ACCESS_KEY"],
        os.environ["AWS_REGION"],
        "execute-api",
        session_token=os.getenv("AWS_SESSION_TOKEN"),
    )

@app.authorizer()
def token_auth(auth_request):
    """
    Custom Authorizer: Provides API Auth using HS512 (HMAC) based Authentication 
    using a Shared Secret Key and an expiring JWT Token.
    Clients invoke the API by sending a Bearer Token.

    # Creating a JWT Token
    issuer = JWT_ISSUER
    expiration = Set token expiration (e.g., 1 hour from now)
     # Create the base payload with required claims
    payload = {
        'iss': issuer,                    # Issuer claim
        'exp': expiration,                # Expiration time
        'iat': datetime.utcnow(),         # Issued at time
    }
    # Create the token with HS512 algorithm
    token = jwt.encode(
        payload=payload,
        key=secret_key,
        algorithm='HS512'
    )

    """
    try:
        # Get the secret from AWS Secrets Manager
        get_secret_value_response = sec_client.get_secret_value(
            SecretId=API_AUTH_SECRET_KEY_NAME
        )

        # Configure validation options
        validation_options = {
            "verify_signature": True,
            "verify_exp": True,        # Verify expiration
            "verify_iss": True,        # Verify issuer
            "require_exp": True,       # Require expiration claim
            "require_iss": True,       # Require issuer claim
            "issuer": MRE_JWT_ISSUER
        }

        # Clean and decode the token
        token = auth_request.token.replace("Bearer", "").strip()
        
        jwt.decode(
            token,
            get_secret_value_response["SecretString"],
            algorithms=["HS512"],
            options=validation_options
        )

        # If successful, return authorized response
        return AuthResponse(routes=[f"/external/*"], principal_id="user")

    except jwt.ExpiredSignatureError:
        return AuthResponse(routes=[""], principal_id="user")
    
    except jwt.InvalidIssuerError:
        return AuthResponse(routes=[""], principal_id="user")
    
    except jwt.InvalidTokenError as e:
        return AuthResponse(routes=[""], principal_id="user")
    
    except Exception as e:
        return AuthResponse(routes=[""], principal_id="user")


@app.route("/external/{proxy+}", cors=True, methods=["GET"], authorizer=token_auth)
def get_payload():
    """
    Invokes the ControlPlane APIs with a GET request. This API is meant for integration with external systems
    that send Bearer JWT tokens for authentication.

    Returns:

        Controlplane API result.

    """

    return invoke_destination_api(
        "GET", app.current_request.uri_params["proxy"], app.current_request.headers
    )


@app.route("/external/{proxy+}", cors=True, methods=["DELETE"], authorizer=token_auth)
def delete_payload():
    """
    Invokes the ControlPlane APIs with a DELETE request. This API is meant for integration with external systems
    that send Bearer JWT tokens for authentication.

    Returns:

        Controlplane API result.

    """
    return invoke_destination_api("DELETE", app.current_request.uri_params["proxy"])


@app.route("/external/{proxy+}", cors=True, methods=["PUT"], authorizer=token_auth)
def put_payload():
    """
    Invokes the ControlPlane APIs with a PUT request. This API is meant for integration with external systems
    that send Bearer JWT tokens for authentication.


    Returns:

        Controlplane API result.

    """
    return invoke_destination_api(
        "PUT",
        app.current_request.uri_params["proxy"],
        api_body=app.current_request.raw_body,
    )


@app.route("/external/{proxy+}", cors=True, methods=["POST"], authorizer=token_auth)
def post_payload():
    """
    Invokes the ControlPlane APIs with a POST request. This API is meant for integration with external systems
    that send Bearer JWT tokens for authentication.


    Returns:

        Controlplane API result.

    """
    return invoke_destination_api(
        "POST",
        app.current_request.uri_params["proxy"],
        api_body=app.current_request.raw_body,
    )


@app.route("/{proxy+}", cors=True, methods=["GET"], authorizer=authorizer)
def get_payload():
    """
    Invokes the ControlPlane APIs with a GET request. Supports IAM Authentication.

    Returns:

        Controlplane API result.

    """
    payload = invoke_destination_api(
        "GET", app.current_request.uri_params["proxy"], app.current_request.headers
    )
    return payload


@app.route("/{proxy+}", cors=True, methods=["DELETE"], authorizer=authorizer)
def delete_payload():
    """
    Invokes the ControlPlane APIs with a DELETE request. Supports IAM Authentication.

    Returns:

        Controlplane API result.

    """
    return invoke_destination_api("DELETE", app.current_request.uri_params["proxy"])


@app.route("/{proxy+}", cors=True, methods=["PUT"], authorizer=authorizer)
def put_payload():
    """
    Invokes the ControlPlane APIs with a PUT request. Supports IAM Authentication.

    Returns:

        Controlplane API result.

    """
    return invoke_destination_api(
        "PUT",
        app.current_request.uri_params["proxy"],
        api_body=app.current_request.raw_body,
    )


@app.route("/{proxy+}", cors=True, methods=["POST"], authorizer=authorizer)
def post_payload():
    """
    Invokes the ControlPlane APIs with a POST request. Supports IAM Authentication.

    Returns:

        Controlplane API result.

    """
    return invoke_destination_api(
        "POST",
        app.current_request.uri_params["proxy"],
        api_body=app.current_request.raw_body,
    )


@app.route("/{proxy+}", cors=True, methods=["PATCH"], authorizer=authorizer)
def post_payload():
    """
    Invokes the ControlPlane APIs with a PATCH request. Supports IAM Authentication.

    Returns:

        Controlplane API result.

    """
    return invoke_destination_api(
        "PATCH",
        app.current_request.uri_params["proxy"],
        api_body=app.current_request.raw_body,
    )


def get_api_url_by_route(uri_params):
    """
    Gets API Endpoint Url based on the Uri Params
    """
    params = uri_params["proxy"].lower()
    if params.startswith("/plugin") or params.startswith("plugin"):
        return SERVICE_ROUTER["PluginUrl"]
    elif params.startswith("/system") or params.startswith("system"):
        return SERVICE_ROUTER["SystemUrl"]
    elif params.startswith("/profile") or params.startswith("profile"):
        return SERVICE_ROUTER["ProfileUrl"]
    elif params.startswith("/model") or params.startswith("model"):
        return SERVICE_ROUTER["ModelUrl"]
    elif params.startswith("/event") or params.startswith("event"):
        return SERVICE_ROUTER["EventUrl"]
    elif params.startswith("/contentgroup") or params.startswith("contentgroup"):
        return SERVICE_ROUTER["ContentGroupUrl"]
    elif params.startswith("/program") or params.startswith("program"):
        return SERVICE_ROUTER["ProgramUrl"]
    elif params.startswith("/workflow") or params.startswith("workflow"):
        return SERVICE_ROUTER["WorkflowUrl"]
    elif params.startswith("/replay") or params.startswith("replay"):
        return SERVICE_ROUTER["ReplayUrl"]
    elif params.startswith("/custompriorities") or params.startswith(
        "custompriorities"
    ):
        return SERVICE_ROUTER["CustomPrioritiesUrl"]
    ## PromptCatalog is optional so we double check it exists here also
    elif (
        params.startswith("/prompt") or params.startswith("prompt")
    ) and SERVICE_ROUTER["PromptCatalogUrl"]:
        return SERVICE_ROUTER["PromptCatalogUrl"]
    else:
        return ""


def invoke_destination_api(api_method, uri_params, api_headers=None, api_body=None):

    try:
        dest_url = get_api_url_by_route(app.current_request.uri_params)

        if not dest_url:
            raise Exception("No route found")

        if api_method in ["GET", "DELETE"]:

            res = requests.request(
                method=api_method,
                url=f"{dest_url}{uri_params}",
                verify=True,
                params=app.current_request.query_params,
                auth=get_iam_auth(),
            )

            if api_headers:
                if "accept" in api_headers:
                    if "application/octet-stream" in api_headers["accept"]:

                        blob_content = json.loads(res.text)
                        return Response(
                            body=bytes(blob_content["BlobContent"], "utf-8"),
                            status_code=200,
                            headers={"Content-Type": "application/octet-stream"},
                        )

        elif api_method in ["PUT", "POST", "PATCH"]:
            res = requests.request(
                method=api_method,
                url=f"{dest_url}{uri_params}",
                headers=api_headers,
                data=api_body,
                verify=True,
                auth=get_iam_auth(),
            )

        res.raise_for_status()

    except requests.HTTPError as e:
        error_msg = get_error_message(e.response.text)
        if res.status_code == 404:
            raise NotFoundError(error_msg)
        elif res.status_code == 400:
            raise BadRequestError(error_msg)
        elif res.status_code == 409:
            raise ConflictError(error_msg)
        elif res.status_code >= 500:
            raise ChaliceViewError(error_msg)
        else:
            raise
    except requests.exceptions.RequestException as e:
        error_msg = get_error_message(e.response.text)
        if res.status_code == 404:
            raise NotFoundError(error_msg)
        elif res.status_code == 400:
            raise BadRequestError(error_msg)
        elif res.status_code == 409:
            raise ConflictError(error_msg)
        elif res.status_code >= 500:
            raise ChaliceViewError(error_msg)
        else:
            raise
    except Exception as e:
        print(e)
        raise
    else:
        return res.content


def get_error_message(error_response):
    try:
        res_json = json.loads(error_response)
        if "message" in res_json:
            return res_json["message"]
        elif "Message" in res_json:
            return res_json["Message"]
    except Exception as e:
        print(e)
    else:
        return error_response

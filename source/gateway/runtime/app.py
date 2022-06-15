import os
from chalice import IAMAuthorizer
from chalice import Chalice, AuthResponse
from chalice import ChaliceViewError, BadRequestError, NotFoundError, ConflictError
import requests
import boto3
from chalice import Response
import json
import jwt

app = Chalice(app_name='aws-mre-gateway-api')
authorizer = IAMAuthorizer()
sd_client = boto3.client('servicediscovery')
session = boto3.session.Session()
sec_client = session.client(
        service_name='secretsmanager'
    )

SERVICE_DISCOVERY_SERVICE_ID = os.environ['SERVICE_DISC_SERVICE_ID']
API_AUTH_SECRET_KEY_NAME = os.environ['API_AUTH_SECRET_KEY_NAME']

def get_iam_auth():
    from requests_aws4auth import AWS4Auth
    return AWS4Auth(
        os.environ['AWS_ACCESS_KEY_ID'],
        os.environ['AWS_SECRET_ACCESS_KEY'],
        os.environ['AWS_REGION'],
        'execute-api',
        session_token=os.getenv('AWS_SESSION_TOKEN')
    )

@app.authorizer()
def token_auth(auth_request):
    '''
        Custom Authorizer: Provides API Auth using HS512 (HMAC) based Authentication using a Shared Secret Key and an expiring JWT Token
        Clients invoke the API by sending a Bearer Token.
    '''

    
    get_secret_value_response = sec_client.get_secret_value(
        SecretId=API_AUTH_SECRET_KEY_NAME
    )
    

    try:
        jwt.decode(auth_request.token.replace("Bearer", '').strip(),
                                     get_secret_value_response['SecretString'], algorithms=["HS512"])
        
    except Exception as e:
        return AuthResponse(routes=[''], principal_id='user')

    
    return AuthResponse(routes=[
        f'/external/*'
    ], principal_id='user')

@app.route('/external/{proxy+}', cors=True, methods=['GET'], authorizer=token_auth)
def get_payload():
    """
    Invokes the ControlPlane APIs with a GET request. This API is meant for integration with external systems
    that send Bearer JWT tokens for authentication.

    Returns:

        Controlplane API result.
            
    """

    return invoke_destination_api("GET", app.current_request.uri_params['proxy'], app.current_request.headers)

@app.route('/external/{proxy+}', cors=True, methods=['DELETE'], authorizer=token_auth)
def delete_payload():
    """
    Invokes the ControlPlane APIs with a DELETE request. This API is meant for integration with external systems
    that send Bearer JWT tokens for authentication.

    Returns:

        Controlplane API result.
            
    """
    return invoke_destination_api("DELETE", app.current_request.uri_params['proxy'])

        
@app.route('/external/{proxy+}', cors=True, methods=['PUT'], authorizer=token_auth)
def put_payload():
    """
    Invokes the ControlPlane APIs with a PUT request. This API is meant for integration with external systems
    that send Bearer JWT tokens for authentication.


    Returns:

        Controlplane API result.
            
    """
    return invoke_destination_api("PUT", app.current_request.uri_params['proxy'], api_body=app.current_request.raw_body)


@app.route('/external/{proxy+}', cors=True, methods=['POST'], authorizer=token_auth)
def post_payload():
    """
    Invokes the ControlPlane APIs with a POST request. This API is meant for integration with external systems
    that send Bearer JWT tokens for authentication.


    Returns:

        Controlplane API result.
            
    """
    return invoke_destination_api("POST", app.current_request.uri_params['proxy'], api_body=app.current_request.raw_body)



@app.route('/{proxy+}', cors=True, methods=['GET'], authorizer=authorizer)
def get_payload():
    """
    Invokes the ControlPlane APIs with a GET request. Supports IAM Authentication.

    Returns:

        Controlplane API result.
            
    """
    payload = invoke_destination_api("GET", app.current_request.uri_params['proxy'], app.current_request.headers)
    return payload

@app.route('/{proxy+}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_payload():
    """
    Invokes the ControlPlane APIs with a DELETE request. Supports IAM Authentication.

    Returns:

        Controlplane API result.
            
    """
    return invoke_destination_api("DELETE", app.current_request.uri_params['proxy'])

@app.route('/{proxy+}', cors=True, methods=['PUT'], authorizer=authorizer)
def put_payload():
    """
    Invokes the ControlPlane APIs with a PUT request. Supports IAM Authentication.

    Returns:

        Controlplane API result.
            
    """
    return invoke_destination_api("PUT", app.current_request.uri_params['proxy'], api_body=app.current_request.raw_body)

@app.route('/{proxy+}', cors=True, methods=['POST'], authorizer=authorizer)
def post_payload():
    """
    Invokes the ControlPlane APIs with a POST request. Supports IAM Authentication.

    Returns:

        Controlplane API result.
            
    """
    return invoke_destination_api("POST", app.current_request.uri_params['proxy'], api_body=app.current_request.raw_body)

def get_url_from_cloudmap(entity):
    service_instances = sd_client.list_instances(ServiceId=SERVICE_DISCOVERY_SERVICE_ID)
    for instance in service_instances['Instances']:
        if entity in instance['Attributes']:
            return instance['Attributes'][entity]

    raise Exception("Service not found")

def get_api_url_by_route(uri_params):
    '''
        Gets API Endpoint Url based on the Uri Params
    '''
    params = uri_params['proxy'].lower()
    if params.startswith('/plugin') or params.startswith('plugin'):
        return get_url_from_cloudmap("PluginUrl")
    elif params.startswith('/system') or params.startswith('system'):
        return get_url_from_cloudmap("SystemUrl")
    elif params.startswith('/profile') or params.startswith('profile'):
        return get_url_from_cloudmap("ProfileUrl")
    elif params.startswith('/model')  or params.startswith('model'):
        return get_url_from_cloudmap("ModelUrl")
    elif params.startswith('/event')  or params.startswith('event'):
        return get_url_from_cloudmap("EventUrl")
    elif params.startswith('/contentgroup') or params.startswith('contentgroup'):
        return get_url_from_cloudmap("ContentGroupUrl")
    elif params.startswith('/program') or params.startswith('program'):
        return get_url_from_cloudmap("ProgramUrl")
    elif params.startswith('/workflow') or params.startswith('workflow'):
        return get_url_from_cloudmap("WorkflowUrl")
    elif params.startswith('/replay') or params.startswith('replay'):
        return get_url_from_cloudmap("ReplayUrl")
    else:
        return ""

def invoke_destination_api(api_method, uri_params, api_headers=None, api_body=None):
    
    try:
            dest_url = get_api_url_by_route(app.current_request.uri_params)
            
            if not dest_url:
                raise Exception("No route found")

            if api_method in ['GET', 'DELETE']:
                
                res = requests.request(
                    method=api_method,
                    url=f"{dest_url}{uri_params}",
                    verify=True,
                    auth=get_iam_auth()
                )

                
                if api_headers: 
                    if 'accept' in api_headers:
                        if 'application/octet-stream' in api_headers['accept']:

                            blob_content = json.loads(res.text)
                            return Response(body=bytes(blob_content['BlobContent'], 'utf-8'),
                                            status_code=200,
                                            headers={'Content-Type': 'application/octet-stream'})

            elif api_method in ['PUT', 'POST']:
                res = requests.request(
                    method=api_method,
                    url=f"{dest_url}{uri_params}",
                    headers=api_headers,
                    data=api_body,
                    verify=True,
                    auth=get_iam_auth()
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
        if 'message' in res_json:
            return res_json['message']
        elif 'Message' in res_json:
            return res_json['Message']
    except Exception as e:
        print(e)
    else:
        return error_response
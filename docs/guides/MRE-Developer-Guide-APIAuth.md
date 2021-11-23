[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Securing MRE API using JWT Tokens

Media Replay Engine (MRE) provides REST APIs which are by default secured using IAM permissions. This means that the API caller (such as another API hosted on API Gateway, a AWS Lambda function, a script executing within an EC2 Instance etc. ) should have the permission to invoke the API method for which the IAM user authentication is enabled. The MRE deployment process ensures that the API consumers have these permissions set automatically. However, if there is a need to integrate MRE API with non AWS Environment hosted systems or services, MRE provides a mechanism to control access to APIs using JWT tokens.

The ControlPlane API implements a custom Lambda authorizer called **jwt_auth**. This Authorizer uses a shared HMAC-SHA512 hash to decode the JWT token passed by the API consumer as a Bearer token. The shared HMAC-SHA512 hash is stored in the AWS Secrets Manager. If the
token is valid, a list of authorized API routes is returned. To control access to new API(s) or existing APIs using JWT tokens, ensure you add the API routes to this Authorized list of routes and register this Authorizer with the API routes using **@app.route**.



```python
@app.authorizer()
def jwt_auth(auth_request):
    '''
        Provides API Auth using HS512 (HMAC) based Authentication using a Shared Secret Key
        and an expiring JWT Token. Clients invoke the API by sending the Bearer JWT Token.
    '''

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager'
    )
    get_secret_value_response = client.get_secret_value(
        SecretId=HLS_HS256_API_AUTH_SECRET_KEY_NAME
    )

    try:
        decoded_payload = jwt.decode(auth_request.token.replace("Bearer", '').strip(),
                             get_secret_value_response['SecretString'], algorithms=["HS512"])
    except Exception as e:
        print(e)
        return AuthResponse(routes=[''], principal_id='user')

    return AuthResponse(routes=[
        '/mre/streaming/auth',
        '/program/*/gameid/*/hls/stream/locations',
        '/event/all/external'
    ], principal_id='user')

```

If you find a need to control access to DataPlane APIs using JWT tokens, follow the same process for the DataPlane APIs.


## Steps to create and pass JWT tokens

In order to create JWT tokens and secure your APIs, follow these steps. This is a Python Sample.

1. Create a SHA512-HMAC secret key using openssl.

```bash
echo | openssl sha512
```

2. Store this SHA512-HMAC secret key within AWS Secrets Manager by updating the value of the secret name **mre_hsa_api_auth_secret**. This secret is automatically created within AWS Secrets Manager when MRE is deployed.

3. API Consumer creates a JWT token by encoding it with the HMAC-SHA512 hash. The following example shows how its done using the PyJwt package in python.

```python
secretkey = HMAC-SHA512 hash
encoded_token = jwt.encode({“exp”: 1629861452, "payLoadKey": "payload"}, secretkey, algorithm=“HS512”)
```
**Note**: Ensure the expiration of JWT is kept to the minimum. You should not keep tokens longer than required.

You can also include a custom payload within the JWT token to implement role based Authorization. In the current implementation, MRE does not provide Role based Authorization. However, you can extend the custom Authorizer and inspect the payload to implement Authorization for APIs.

4. Pass the JWT token in the Authorization header using the Bearer schema to gain access to the protected API.  The content of the header should look like the following:

```html
Authorization: Bearer <token>
```

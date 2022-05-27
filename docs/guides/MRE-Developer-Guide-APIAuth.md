[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Securing MRE ControlPlane API using JWT Tokens

Media Replay Engine (MRE) provides REST APIs which are by default secured using IAM permissions. So API consumers (such as another API hosted on API Gateway, a AWS Lambda function, a script executing within an EC2 Instance etc. ) should have permission to invoke the API secured using IAM user authentication. The MRE deployment process ensures that API consumers within MRE have these permissions set automatically. However, if there is a need to consume these API from non AWS Environment hosted systems or services, MRE provides a mechanism to control access to APIs using JWT tokens.

MRE provides a API Proxy (Gateway) which serves as a single API gateway to several ControlPlane APIs. The Proxy forwards API requests to ControlPlane APIs based on the API route. Consumers are required to use this Gateway API when integrating with ControlPlane API. Refer to the [Gateway API](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/gateway.html)
 documentation for more details.


The Gateway API implements a custom Lambda authorizer called **token_auth**. This Authorizer uses a shared HMAC-SHA512 hash to decode the JWT token passed by the API consumer as a Bearer token. The shared HMAC-SHA512 hash is stored in the AWS Secrets Manager. If the
token is valid, the Gateway forwards API requests to the ControlPlane APIs. 



```python
@app.authorizer()
def token_auth(auth_request):
    '''
        Custom Authorizer: Provides API Auth using HS512 (HMAC) based Authentication 
        using a Shared Secret Key and an expiring JWT Token
        Clients invoke the API by sending a Bearer Token.
    '''

    
    get_secret_value_response = sec_client.get_secret_value(
        SecretId=API_AUTH_SECRET_KEY_NAME
    )

    try:
        decoded_payload = jwt.decode(auth_request.token.replace("Bearer", '').strip(),
                                     get_secret_value_response['SecretString'], algorithms=["HS512"])
    except Exception as e:
        return AuthResponse(routes=[''], principal_id='user')

    return AuthResponse(routes=[
        '/external/*'
    ], principal_id='user')

```

## Steps to create and pass JWT tokens to MRE Gateway API

In order to create JWT tokens and secure your APIs, follow these steps. This is a Python Sample.

1. Create a SHA512-HMAC secret key using openssl.

```bash
echo | openssl sha512
```

2. Store this SHA512-HMAC secret key within AWS Secrets Manager by updating the value of the secret name **mre_hsa_api_auth_secret**. This secret name is automatically created within AWS Secrets Manager when MRE is deployed.

3. API Consumer creates a JWT token by encoding it with the HMAC-SHA512 hash. The following example shows how its done using the PyJwt package in python.

```python
import jwt
secretkey = HMAC-SHA512 hash
encoded_token = jwt.encode({“exp”: 1629861452, "payLoadKey": "payload"}, secretkey, algorithm=“HS512”)
```
**Note**: Ensure the expiration of JWT is kept to the minimum. You should not keep tokens longer than required.

You can also include a custom payload within the JWT token to implement role based Authorization. In the current implementation, MRE does not provide Role based Authorization. However, you can extend the custom Authorizer and inspect the payload to implement Authorization for APIs.

4. Pass the JWT token in the Authorization header using the Bearer schema to gain access to the protected API.  The content of the header should look like the following:

```html
Authorization: Bearer <token>
```

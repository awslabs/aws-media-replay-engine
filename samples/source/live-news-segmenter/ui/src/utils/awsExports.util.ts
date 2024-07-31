import { environments } from './env.util';

export const awsmobile = {
    "aws_project_region": environments.APP_REGION,
    "aws_cognito_identity_pool_id": environments.APP_IDENTITY_POOL_ID,
    "aws_cognito_region": environments.APP_REGION,
    "aws_user_pools_id": environments.APP_USER_POOL_ID,
    "aws_user_pools_web_client_id": environments.APP_CLIENT_ID,
    "oauth": {},
    "aws_cognito_username_attributes": [
        "EMAIL"
    ],
    "aws_cognito_social_providers": [],
    "aws_cognito_signup_attributes": [
        "EMAIL"
    ],
    "aws_cognito_mfa_configuration": "OFF",
    "aws_cognito_mfa_types": [
        "SMS"
    ],
    "aws_cognito_verification_mechanisms": [
        "EMAIL"
    ]
}

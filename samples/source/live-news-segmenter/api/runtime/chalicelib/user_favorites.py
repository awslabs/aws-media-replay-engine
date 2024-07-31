import os
import json
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
from chalice import IAMAuthorizer
from chalice import Blueprint, Response, ChaliceViewError
from boto3.dynamodb.conditions import Key


authorizer = IAMAuthorizer()
user_favorites_api = Blueprint(__name__)

USER_FAVORITES_TABLE_NAME = os.environ['USER_FAVORITES_TABLE_NAME']
ddb_resource = boto3.resource("dynamodb")
user_favorites_table = ddb_resource.Table(USER_FAVORITES_TABLE_NAME)


@user_favorites_api.route('/customapi/user-favorites/{program}/{event}/{user_name}', cors=True, methods=['POST', 'PUT'], authorizer=authorizer)
def create_user_favorites(program, event, user_name):
    """
    This function is responsible for creating a new user favorite in the DynamoDB table.

    Parameters:
    program (str): The program name.
    event (str): The event name.
    user_name (str): The user's name.

    request format: /customapi/user-favorites/{program}/{event}/{user_name}
    Sample request: /customapi/user-favorites/full-sotu1/2023_State_Of_The_Union/cesar.reyes
    headers: Content-Type=application/json
    Sample Body: {"start": "190.32", "comments": "test comments"}
    the comments field is optional.
    
    Previous lambda: insertUserFavorites
    
    Returns:
    dict: A dictionary containing the status of the operation.

    Raises:
    ChaliceViewError: If there is an error while inserting the user favorite.
    """
    try:
        request = user_favorites_api.current_request
        body = json.loads(request.raw_body.decode())
        comments = ""
        start = Decimal(str(body['start']))
    
        if "comments" in body:
            comments = body["comments"]
        
        response = user_favorites_table.put_item(
            Item={
                'program-event-user': f'{program}#{event}#{user_name}',
                'start': start,
                'comments': comments
            }
        )
        
        return {
            "Items": 'success'
        }
    except ClientError as err:
        err_msg = f"Unable insert the user favorite : {str(err)}"
        print(err_msg)
        raise ChaliceViewError(err_msg)
    
@user_favorites_api.route('/customapi/user-favorites/{program}/{event}/{user_name}', cors=True, methods=['GET'], authorizer=authorizer)
def get_user_favorites(program, event, user_name):
    """
    This function is responsible for getting the user favorites from the DynamoDB table.

    Parameters:
    program (str): The program name.
    event (str): The event name.
    user_name (str): The user's name.

    request format: /customapi/user-favorites/{program}/{event}/{user_name}
    Sample request: /customapi/user-favorites/full-sotu1/2023_State_Of_The_Union/cesar.reyes
    headers: Content-Type=application/json
    
    Previous lambda: getUserFavorites
    
    Returns:
    dict: A dictionary containing the user favorites.

    Raises:
    ChaliceViewError: If there is an error while getting the user favorites.
    """
    try:
        response = user_favorites_table.query(
            KeyConditionExpression=Key('program-event-user').eq(f'{program}#{event}#{user_name}'),
            ScanIndexForward=False
        )
                
        return {
            "Count": response["Count"],
            "ScannedCount": response["ScannedCount"],
            "Items": response["Items"]
        }
    except ClientError as err:
        err_msg = f"Unable get the user favorites : {str(err)}"
        print(err_msg)
        raise ChaliceViewError(err_msg)
    
@user_favorites_api.route('/customapi/user-favorites/{program}/{event}/{user_name}/{start}', cors=True, methods=['DELETE'], authorizer=authorizer)
def delete_user_favorites(program, event, user_name, start):
    """
    This function is responsible for deleting the user favorites from the DynamoDB table.

    Parameters:
    program (str): The program name.
    event (str): The event name.
    user_name (str): The user's name.
    start (str): The start time.

    request format: /customapi/user-favorites/{program}/{event}/{user_name}/{start_time}
    Sample request: /customapi/user-favorites/full-sotu1/2023_State_Of_The_Union/cesar.reyes/190.32
    headers: Content-Type=application/json
    
    Previous lambda: deleteUserFavorites
    
    Returns:
    dict: A dictionary containing the status of the operation.

    Raises:
    ChaliceViewError: If there is an error while deleting the user favorites.
    """
    try:
        response = user_favorites_table.delete_item(
            Key={
                'program-event-user': f'{program}#{event}#{user_name}',
                'start':  Decimal(str(start))
            }
        )
        
        return {
            "Items": 'success'
        }
    except ClientError as err:
        err_msg = f"Unable delete the user favorites : {str(err)}"
        print(err_msg)
        raise ChaliceViewError(err_msg)
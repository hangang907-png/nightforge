import base64
import hashlib
import hmac
import json

from nightforge.lambda_handler import create_lambda_handler


class ConditionalCheckFailedException(Exception):
    pass


class FakeDynamoDB:
    def __init__(self):
        self.items = {}
        self.exceptions = type("Exceptions", (), {"ConditionalCheckFailedException": ConditionalCheckFailedException})

    def put_item(self, *, Item, ConditionExpression):
        assert ConditionExpression == "attribute_not_exists(delivery_id)"
        delivery_id = Item["delivery_id"]
        if delivery_id in self.items:
            raise ConditionalCheckFailedException()
        self.items[delivery_id] = Item


def _event(payload, headers):
    return {
        "requestContext": {"http": {"method": "POST", "path": "/webhook"}},
        "headers": headers,
        "isBase64Encoded": True,
        "body": base64.b64encode(payload).decode("ascii"),
    }


def test_lambda_receiver_records_signed_ping_and_rejects_duplicate():
    payload = b'{"zen":"keep it logically awesome"}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    dynamodb = FakeDynamoDB()
    handler = create_lambda_handler("secret", "owner/repo", dynamodb)
    event = _event(
        payload,
        {
            "X-GitHub-Delivery": "ping-1",
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": signature,
        },
    )

    accepted = handler(event, None)
    duplicate = handler(event, None)

    assert accepted["statusCode"] == 202
    assert json.loads(accepted["body"])["accepted"] is True
    assert dynamodb.items["ping-1"]["event"] == "ping"
    assert duplicate["statusCode"] == 200
    assert json.loads(duplicate["body"])["duplicate"] is True


def test_lambda_receiver_rejects_wrong_path_before_processing():
    handler = create_lambda_handler("secret", "owner/repo", FakeDynamoDB())

    response = handler({"requestContext": {"http": {"method": "GET", "path": "/wrong"}}}, None)

    assert response == {"statusCode": 404, "headers": {"content-type": "application/json"}, "body": '{"error": "not found"}'}

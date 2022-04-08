[![Header](../assets/images/mre-header-1.png)](../../MRE-Developer-Guide.md)

# Developers Guide - Events

## Creating events with automation

Events can be automatically synchronized with your EPG data source using a provided MRE API. A queue is advised to bridge live EPG update sources to MRE where a Lambda function can filter as desired.

![create-events](../assets/images/devguide-create-events.png)

As it relates to managing events in the **MRE Console** you can:
- Add an event
- Delete an event
- View events

Using the **MRE API** you can:
- Add an event
- Update an event
- Delete an event
- View events
- Search for events and more

Before creating an event, consider two attributes that are helpful to organize them in MRE. The attribute **Program** groups events. An example is a large multi-day tournament that can be set as the **Program** name (2022 Winter Olympics).

The payload to the **event** API takes a payload that is described here:

[POST /event](https://htmlpreview.github.io/?https://github.com/awslabs/aws-media-replay-engine/blob/main/docs/source/output/api/controlplane-event.html#create-event)

Below are Python code snippets that are useful to perform the  

```
def update_event(event_name, program, event_payload):
    path = f"/event/{event_name}/program/{program}"
    method = "PUT"
    event_headers = {
        "Content-Type": "application/json"
    }
    return invoke_api(path, method,headers=event_headers, body=json.dumps(event_payload))

def get_event(event_name, program):
    path = f"/event/{event_name}/program/{program}"
    method = "GET"
    event_headers = {
        "Content-Type": "application/json"
    }
    return invoke_api(path, method,headers=event_headers)

def create_event(event_payload):
    path = "/event"
    method = "POST"
    event_headers = {
        "Content-Type": "application/json"
    }
    return invoke_api(path, method,headers=event_headers, body=json.dumps(event_payload))
```

# DetectExternalData #

**MRE Plugin Class**
- Featurer

**Description**:

This plugin looks up data from an external (to MRE) data source in DynamoDB for each chunk processed. It is provided as a sample to be modified for your needs.

**Use Cases**:
- Looking up supplemental data from a third-party source and aligning it with clips detected by MRE
- Integrating IoT sensor data from game elements (balls, players, rackets, sticks, etc)

**Dependencies**:
- MRE Helper libraries
- Boto3

**ML Model dependencies**:
- None

**Other plugin dependencies**:
- None

**Parameter inputs**:
- lookup_ddb_table >> Your dynamodb table that has your data to query around timestamps.
- game_id >> A value to filter the table by - this may not be needed or solved another way as you like.

**Output attributes**:
- Label
- touchdown
- extra_point
- field_goal
- rush_below_10_yards
- rush_between_10_and_20_yards
- rush_above_20_yards
- pass_completion_below_10_yards
- pass_completion_between_10_and_20_yards
- pass_completion_above_20_yards

**IAM permissions (least privilege)**:
- dynamodb:Query *

**Before you run**:
- Set up and populate a Amazon DynamoDB table with the external data your will be pulling from.
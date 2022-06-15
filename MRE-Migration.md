# MRE Migration

- [From version 1.0.x to 2.x.x](#from-version-1.0.x-to-2.x.x)
  - [Data Migration](#data-migration)
  - [API Consumption](#api-consumption)
  - [Custom Plugins](#custom-plugins)

## From version 1.0.x to 2.x.x

### Data Migration

Due to the new micro services architecture of the MRE Control plane, the names of DynamoDB tables and S3 buckets used by MRE have changed between version 1.0.x and 2.x.x. The migration path involves migrating data from v1.0.x DynamoDB tables and objects within v1.0.x S3 buckets to the resources used by v2.x.x.

We suggest that AWS Glue be used to migrate data from the Source to the Target DynamoDB table. Please refer to the instructions for setting up [AWS Glue jobs](https://docs.aws.amazon.com/prescriptive-guidance/latest/dynamodb-full-table-copy-options/aws-glue.html) to migrate data from source to target tables.

**AWS Glue ETL**

While data migration for many tables can follow the Extract -> Load pattern, few tables would require that data be Transformed before loading data into Target tables. The data transformation is related to the change in S3 bucket names.Glue jobs need to dynamically update the bucket names (from v1.0.x) with the new bucket names (from v2.x.x) during the ETL process.

The following table maps the DynamoDB Table names from the previous version of MRE to the current version as well as the bucket names that need to be transformed during the ETL process.

| Source table name prefix - v1.0.x | Target table name prefix - v2.x.x | Bucket name to be changed (Source -> Target) |
| --- | --- | --- |
| aws-mre-controlplane-ReplayRequest* | aws-mre-controlplane-replay-ReplayRequest* | MreMediaOutputbucket* -> MreMediaOutputbucket* |
| aws-mre-dataplane-Chunk* | aws-mre-dataplane-Chunk* | MediaLiveDestinationbucket* -> MreMediaSourcebucket* |
| aws-mre-dataplane-ClipReviewFeedback* | aws-mre-dataplane-ClipReviewFeedback* | - | - |
| aws-mre-dataplane-Frame* | aws-mre-dataplane-Frame* | - | - |
| aws-mre-dataplane-PluginResult* | aws-mre-dataplane-PluginResult* | MediaLiveDestinationbucket* -> MreMediaSourcebucket* |
| aws-mre-dataplane-ReplayResults* | aws-mre-dataplane-ReplayResults* | - | - |
| aws-mre-controlplane-ContentGroup* | aws-mre-shared-resources-ContentGroup* | - | - |
| aws-mre-controlplane-CurrentEvents* | aws-mre-shared-resources-CurrentEvents*| - | - |
| aws-mre-controlplane-Event* | aws-mre-shared-resources-Event* |MreDataExportbucket* -> MreDataExportbucket* |
| aws-mre-controlplane-Model* | aws-mre-shared-resources-Model* | - | - |
| aws-mre-controlplane-Plugin* | aws-mre-shared-resources-Plugin* | - | - |
| aws-mre-controlplane-Profile* | aws-mre-shared-resources-Profile* | - | - |
| aws-mre-controlplane-Program* | aws-mre-shared-resources-Program* | - | - |
| aws-mre-controlplane-System* | aws-mre-shared-resources-System* | - | - |
| aws-mre-controlplane-WorkflowExecution* | aws-mre-shared-resources-WorkflowExecution* | - | - |


**Migrate S3 Objects**

Objects from the following v1.0.x S3 buckets need to be migrated into the new v2.x.x S3 buckets. Refer to these [instructions](https://aws.amazon.com/premiumsupport/knowledge-center/move-objects-s3-bucket/) for copying all objects from one S3 bucket to another.


| Bucket name prefix - v1.0.x | Bucket name prefix - v2.x.x |
| --- | -- |
| MediaLiveDestinationbucket* | MreMediaSourcebucket* |
| MreDataExportbucket* | MreDataExportbucket* |
| MreMediaOutputbucket* | MreMediaOutputbucket* |

### API Consumption

Consumers of existing MRE Controlplane API need to consume the newly developed aws-mre-gateway-api endpoint.

### Custom Plugins

If you have developed custom plugins using the v1.0.x Lambda layers, make sure the custom Plugins are redeployed referencing the v2.x.x Lambda layers. You will need to re-register these Plugins within MRE.
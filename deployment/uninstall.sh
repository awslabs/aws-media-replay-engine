###############################################################################
# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
###############################################################################

#########################
# Stack Deletion Script #
#########################

# Function to delete a CloudFormation stack and wait for completion
# if the stack does not exist, do not throw an error
delete_stack() {
    if aws cloudformation describe-stacks --stack-name "$1" > /dev/null 2>&1; then
        echo "Deleting stack: $1"
        aws cloudformation delete-stack --stack-name "$1" || true
        echo "Waiting for stack deletion to complete: $1"
        aws cloudformation wait stack-delete-complete --stack-name "$1" || true
        
        # Check if stack still exists and its status after wait completes or times out
        if aws cloudformation describe-stacks --stack-name "$1" > /dev/null 2>&1; then
            # Get the stack status
            stack_status=$(aws cloudformation describe-stacks --stack-name "$1" --query "Stacks[0].StackStatus" --output text)
            if [[ $stack_status == *"FAILED"* || $stack_status == *"IN_PROGRESS"* ]]; then
                echo "WARNING: Stack deletion failed or is still in progress: $1 (Status: $stack_status)"
                echo "You may need to manually resolve issues with this stack in the AWS Console."
            else
                echo "Stack status after wait: $1 (Status: $stack_status)"
            fi
        else
            echo "Stack deletion complete: $1"
        fi
    else
        echo "Stack does not exist: $1, skipping..."
    fi
}

#######################
# Frontend Resources #
#######################

# Delete MRE Frontend stack
echo "Starting deletion of MRE Frontend stack..."
delete_stack "mre-frontend-stack"

#######################
# Gateway Resources  #
#######################

# Delete Gateway stack 
echo "Starting deletion of Gateway stack..."
delete_stack "aws-mre-gateway"

#######################
# GenAI Search        #
#######################

# Delete GenAI Search stack 
echo "Starting deletion of Gateway GenAI Search stack..."
delete_stack "aws-mre-genai-search"

#######################
# Dataplane Resources #
#######################

# Delete Dataplane stack
echo "Starting deletion of Dataplane stack..."
delete_stack "aws-mre-dataplane"

#########################
# Controlplane Resources #
#########################

# Delete Controlplane stacks in order
echo "Starting deletion of Controlplane stacks..."
declare -a controlplane_stacks=(
    "aws-mre-controlplane-replay"
    "aws-mre-controlplane-event"
    "aws-mre-controlplane-workflow"
    "aws-mre-controlplane-profile"
    "aws-mre-controlplane-prompt-catalog"
    "aws-mre-controlplane-plugin"
    "aws-mre-controlplane-model"
    "aws-mre-controlplane-system"
    "aws-mre-controlplane-contentgroup"
    "aws-mre-controlplane-program"
    "aws-mre-controlplane-custompriorities"
)

for stack in "${controlplane_stacks[@]}"; do
    delete_stack "$stack"
done



#######################
# Service Resources  #
#######################

# Delete remaining stacks in order
echo "Starting deletion of remaining service stacks..."
declare -a stacks=(
    "aws-mre-workflow-trigger"
    "aws-mre-replay-handler"
    "aws-mre-event-scheduler" 
    "aws-mre-event-life-cycle"
    "aws-mre-data-exporter"
    "aws-mre-clip-generation"
    "aws-mre-segment-caching"
    "aws-mre-shared-resources"
)

for stack in "${stacks[@]}"; do
    delete_stack "$stack"
done

echo "Cleanup complete!"

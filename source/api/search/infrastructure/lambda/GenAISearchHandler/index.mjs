/**
 * Copyright 2024 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import util from "util";
import stream from "stream";
import { defaultProvider } from "@aws-sdk/credential-provider-node";
import { Client } from "@opensearch-project/opensearch";
import { AwsSigv4Signer } from "@opensearch-project/opensearch/aws";
import { DynamoDBClient, GetItemCommand } from "@aws-sdk/client-dynamodb";
import { BedrockClient, ListInferenceProfilesCommand } from "@aws-sdk/client-bedrock";
import {
  BedrockRuntimeClient,
  ConverseStreamCommand,
  InvokeModelCommand,
} from "@aws-sdk/client-bedrock-runtime";
import { HumanMessage, AIMessage } from "@langchain/core/messages";
import { DynamoDBChatMessageHistory } from "@langchain/community/stores/message/dynamodb";

const aossDetailSearchEndpoint =
  process.env["OPENSEARCH_DETAILSEARCH_ENDPOINT"];
const aossDetailSearchIndex = process.env["OPENSEARCH_DETAILSEARCH_INDEX"];
const genAISearchPromptName = process.env["GENAI_SEARCH_PROMPT_NAME"];
const genAISearchModelId =
  process.env["GENAI_SEARCH_MODEL_ID"] || "amazon.nova-pro-v1:0";
const temperature = parseFloat(process.env["TEMPERATURE"]) || 0.5;
const maxTokens = parseInt(process.env["MAX_TOKENS"]) || 4096;
const systemTableName = process.env["SYSTEM_TABLE_NAME"];
const conversationHistoryTableName =
  process.env["CONVERSATION_HISTORY_TABLE_NAME"];
const ossQuerySize = parseInt(process.env["OSS_QUERY_SIZE"]);
const ossQueryKValue = parseInt(process.env["OSS_QUERY_K_VALUE"]);
const embeddingsModelId =
  process.env["EMBEDDINGS_MODEL_ID"] || "amazon.titan-embed-text-v2:0";
const pipeline = util.promisify(stream.pipeline);
const ddbClient = new DynamoDBClient({ region: process.env.AWS_REGION });
const bedrockClient = new BedrockClient({
  region: process.env.AWS_REGION,
});
const bedrockRuntime = new BedrockRuntimeClient({
  region: process.env.AWS_REGION,
  maxAttempts: 10,
  retryMode: "adaptive",
});
const aossClient = new Client({
  ...AwsSigv4Signer({
    region: process.env.AWS_REGION,
    service: "aoss",
    getCredentials: () => {
      const credentialsProvider = defaultProvider();
      return credentialsProvider();
    },
  }),
  node: aossDetailSearchEndpoint,
});
// Tool definitions
const toolConfig = {
  tools: [
    {
      toolSpec: {
        name: "calculator",
        description:
          "A simple calculator that performs basic arithmetic operations.",
        inputSchema: {
          json: {
            type: "object",
            properties: {
              expression: {
                type: "string",
                description:
                  "The mathematical expression to evaluate (e.g., '2 + 3 * 4').",
              },
            },
            required: ["expression"],
          },
        },
      },
    },
    {
      toolSpec: {
        name: "number_compare",
        description:
          "Compares two numbers and returns if they are equal to one another, if the first number is greater than the second number, or if the first number is less than the second number. Input should be valid numbers and the tool will not perform any arithmetic operations.",
        inputSchema: {
          json: {
            type: "object",
            properties: {
              firstNumber: {
                type: "number",
                description: "First number to compare.",
              },
              secondNumber: {
                type: "number",
                description: "Second number to compare.",
              },
            },
            required: ["firstNumber", "secondNumber"],
          },
        },
      },
    },
    {
      toolSpec: {
        name: "sort_list_by_key",
        description:
          "Sorts a list of JSON objects by a given key in ascending order. Input should be a list of JSON objects to sort and the key to sort by.",
        inputSchema: {
          json: {
            type: "object",
            properties: {
              list: {
                type: "array",
                items: {
                  type: "object",
                },
                description: "List of JSON objects to sort.",
              },
              key: {
                type: "string",
                description: "Key to sort by.",
              },
            },
            required: ["list", "key"],
          },
        },
      },
    },
  ],
  toolChoice: {
    auto: {},
  },
};
function calculatorTool({ expression }) {
  const expr = expression.replace(/[^0-9+\-*/().]/g, "");
  const indirectEval = Function("return eval('" + expr + "');");
  const result = indirectEval();
  return result.toString();
}
function numberCompareTool({ firstNumber, secondNumber }) {
  const result = Math.sign(firstNumber - secondNumber);
  switch (result) {
    case 1:
      return `${firstNumber} is greater than ${secondNumber}.`;
    case 0:
      return `${firstNumber} is equal to ${secondNumber}.`;
    case -1:
      return `${firstNumber} is less than ${secondNumber}.`;
    default:
      throw new Error("Invalid comparison result");
  }
}
function sortListByKeyTool({ list, key }) {
  const sortedList = list.sort((a, b) => {
    if (a[key] < b[key]) {
      return -1;
    }
    if (a[key] > b[key]) {
      return 1;
    }
    return 0;
  });
  return JSON.stringify(sortedList);
}
const selectedTool = {
  calculator: calculatorTool,
  number_compare: numberCompareTool,
  sort_list_by_key: sortListByKeyTool,
};

async function getInferenceProfileId(modelId) {
  let command = new ListInferenceProfilesCommand({
    typeEquals: "SYSTEM_DEFINED",
  });
  let response = await bedrockClient.send(command);
  const profileSummaries = response.inferenceProfileSummaries;
  // Perform pagination as long as nextToken is present in the response
  while (response.nextToken) {
    command.nextToken = response.nextToken;
    response = await bedrockClient.send(command);
    profileSummaries.push(...response.inferenceProfileSummaries);
  }
  for (const profileSummary of profileSummaries) {
    if (
      profileSummary.inferenceProfileId.endsWith(modelId) &&
      profileSummary.status === "ACTIVE"
    ) {
      console.log(
        `Found inference profile: ${profileSummary.inferenceProfileId}`
      );
      return profileSummary.inferenceProfileId;
    }
  }
  return modelId;
}

async function getValueFromSystemTable(name) {
  const params = {
    TableName: systemTableName,
    Key: {
      Name: {
        S: name,
      },
    },
  };
  const command = new GetItemCommand(params);
  try {
    const response = await ddbClient.send(command);
    return response.Item?.Value.S ?? null;
  } catch (error) {
    console.error("Error fetching value from System DDB table:", error);
    return null;
  }
}

async function streamMessages(
  systemMessage,
  modelId,
  messages,
  responseStream
) {
  const input = {
    modelId: modelId,
    messages: messages,
    system: systemMessage,
    inferenceConfig: {
      temperature: temperature,
      maxTokens: maxTokens,
    },
    toolConfig: toolConfig,
  };
  const command = new ConverseStreamCommand(input);
  const response = await bedrockRuntime.send(command);
  let toolUse = {},
    text = "";
  const message = {},
    content = [];
  message.content = content;
  for await (const stream of response.stream) {
    console.log(`Stream: ${JSON.stringify(stream)}`);
    if (stream.messageStart) {
      message.role = stream.messageStart.role;
    } else if (stream.contentBlockStart) {
      const tool = stream.contentBlockStart.start.toolUse;
      toolUse.toolUseId = tool.toolUseId;
      toolUse.name = tool.name;
    } else if (stream.contentBlockDelta) {
      const delta = stream.contentBlockDelta.delta;
      if (delta.toolUse) {
        if (!("input" in toolUse)) {
          toolUse.input = "";
        }
        toolUse.input += delta.toolUse.input;
      } else if (delta.text) {
        responseStream.write(delta.text);
        console.log(`Token: ${delta.text}`);
        text += delta.text;
      }
    } else if (stream.contentBlockStop) {
      if (toolUse.input) {
        toolUse.input = JSON.parse(toolUse.input);
        content.push({ toolUse: toolUse });
        toolUse = {};
      } else {
        content.push({ text: text });
        text = "";
      }
    } else if (stream.messageStop) {
      stopReason = stream.messageStop.stopReason;
    }
  }
  return { stopReason, message };
}

async function converseStream(
  systemMessage,
  ddbMessageHistory,
  modelId,
  prompt,
  responseStream
) {
  const messages = [
    {
      role: "user",
      content: [{ text: prompt }],
    },
  ];
  // Save the user message in chat history
  await ddbMessageHistory.addMessage(new HumanMessage({ content: prompt }));
  let { stopReason, message } = await streamMessages(
    systemMessage,
    modelId,
    messages,
    responseStream
  );
  messages.push(message);
  let aiMessage = message.content[0].text;
  // Tool calling
  while (stopReason === "tool_use") {
    for (const content of message.content) {
      if (content.toolUse) {
        const tool = content.toolUse;
        const toolResult = {};
        console.log(`Tool call: ${JSON.stringify(tool)}`);
        try {
          const toolOutput = await selectedTool[tool.name](tool.input);
          console.log(`Tool output: ${toolOutput}`);
          toolResult.toolUseId = tool.toolUseId;
          toolResult.content = [{ text: toolOutput }];
        } catch (error) {
          console.log(`Tool output: ${error.message}`);
          toolResult.toolUseId = tool.toolUseId;
          toolResult.content = [{ text: error.message }];
          toolResult.status = "error";
        }
        messages.push({
          role: "user",
          content: [
            {
              toolResult: toolResult,
            },
          ],
        });
      }
    }
    ({ stopReason, message } = await streamMessages(
      systemMessage,
      modelId,
      messages,
      responseStream
    ));
    messages.push(message);
    aiMessage += message.content[0].text;
  }
  // Save the assistant message in chat history
  await ddbMessageHistory.addMessage(new AIMessage({ content: aiMessage }));
  responseStream.end();
}

async function getContextFromVectorDB(eventName, programName, queryEmbeddings) {
  const filter = { bool: { must: [] } };
  if (eventName) {
    filter["bool"]["must"].push({ match_phrase: { Event: eventName } });
  }
  if (programName) {
    filter["bool"]["must"].push({ match_phrase: { Program: programName } });
  }
  const searchQuery = {
    size: ossQuerySize,
    query: {
      knn: {
        embedding: {
          vector: queryEmbeddings,
          k: ossQueryKValue,
          filter: filter,
        },
      },
    },
    _source: false,
    fields: ["content", "Program", "Event"],
  };
  const response = await aossClient.search({
    index: aossDetailSearchIndex,
    body: searchQuery,
  });
  let contentString = "";
  response.body.hits.hits.forEach((hit) => {
    hit.fields.content.forEach((content) => {
      contentString +=
        content.replace("<Record>", "").replace("</Record>", "") + " ";
    });
  });
  console.log(`sbc=${contentString}`);
  return contentString;
}

async function generateEmbeddings(body) {
  const input = {
    body: body,
    contentType: "application/json",
    accept: "application/json",
    modelId: embeddingsModelId,
  };
  const command = new InvokeModelCommand(input);
  const response = await bedrockRuntime.send(command);
  const jsonString = new TextDecoder().decode(response.body);
  return JSON.parse(jsonString);
}

async function handleEvent(event, responseStream) {
  const body = JSON.parse(event.body);
  const sessionId = body.SessionId;
  const ddbMessageHistory = new DynamoDBChatMessageHistory({
    tableName: conversationHistoryTableName,
    sessionId: sessionId,
    partitionKey: "SessionId",
  });
  const programName = body.Program;
  const eventName = body.Event;
  const query = body.Query;
  const modelId = await getInferenceProfileId(
    body.ModelId ||
      (await getValueFromSystemTable("GENAI_SEARCH_MODEL_ID")) ||
      genAISearchModelId
  );
  const embeddingBody = JSON.stringify({
    inputText: query,
    dimensions: 1024,
  });
  const queryEmbeddings = await generateEmbeddings(embeddingBody);
  const searchResultContext = await getContextFromVectorDB(
    eventName,
    programName,
    queryEmbeddings.embedding
  );
  console.log(`Model: ${modelId}`);
  console.log(`Context: ${searchResultContext}`);
  let systemPrompt =
    "You are an expert in video analysis and your job is to answer the user question after thoroughly analyzing all the data available in the context about a video and if applicable, the chat history.\n" +
    "You have access to the following tools and you should always make use of them during your analysis:\n" +
    "1) calculator tool if you want to perform basic arithmetic operations on two or more numbers.\n2) number_compare tool if you want to compare two numbers such as two start timings, two end timings, start and end timings, or any two numbers in general to determine which of them is smaller or greater.\n3) sort_list_by_key tool if you want to sort a list of JSON objects by a specific key in ascending order (for example, to sort the sentence group list in your final response by the Start key).\n\n";
  const chatHistory = await ddbMessageHistory.getMessages();
  if (chatHistory.length > 0) {
    systemPrompt += `Here is the chat history of the ongoing conversation:\n<chat_history>\n${JSON.stringify(
      chatHistory
    )}\n</chat_history>\n\n`;
  }
  const systemMessage = [
    {
      text: systemPrompt,
    },
  ];
  const ddbPrompt = await getValueFromSystemTable(genAISearchPromptName);
  const modifiedDdbPrompt = ddbPrompt
    .replace("{context}", searchResultContext)
    .replace("{question}", query);
  console.log(`GenAI Search Prompt: ${modifiedDdbPrompt}`);
  await converseStream(
    systemMessage,
    ddbMessageHistory,
    modelId,
    modifiedDdbPrompt,
    responseStream
  );
}

export const handler = awslambda.streamifyResponse(
  async (event, responseStream, _context) => {
    console.log(`Lambda got the following event: \n ${JSON.stringify(event)}`);

    const requestContext = event["requestContext"];
    const path = requestContext["http"]["path"];
    const method = requestContext["http"]["method"];

    if (method === "POST" && path === "/") {
      await handleEvent(event, responseStream);
    } else {
      await pipeline(
        JSON.stringify({
          statusCode: 404,
          body: `${method} on ${path} is not implemented`,
        }),
        responseStream
      );
    }
  }
);

const AWS = require("aws-sdk");
const sqs = new AWS.SQS({ region: "me-central-1" });

// SQS Queue URL
const QUEUE_URL = "https://sqs.me-central-1.amazonaws.com/257394457473/whatsapp-user001-commands";

exports.handler = async (event) => {
  console.log("API Handler with SQS received event:", JSON.stringify(event, null, 2));
  
  try {
    // Send message to SQS
    const messageBody = {
      timestamp: new Date().toISOString(),
      path: event.path,
      method: event.httpMethod,
      body: event.body ? JSON.parse(event.body) : {},
      headers: event.headers
    };
    
    const sqsParams = {
      QueueUrl: QUEUE_URL,
      MessageBody: JSON.stringify(messageBody)
    };
    
    console.log("Sending message to SQS:", sqsParams);
    const sqsResult = await sqs.sendMessage(sqsParams).promise();
    console.log("SQS send result:", sqsResult);
    
    return {
      statusCode: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      },
      body: JSON.stringify({
        message: "Message sent to SQS successfully\!",
        messageId: sqsResult.MessageId,
        timestamp: new Date().toISOString()
      })
    };
  } catch (error) {
    console.error("Error sending to SQS:", error);
    return {
      statusCode: 500,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
      },
      body: JSON.stringify({
        error: "Failed to send message to SQS",
        details: error.message
      })
    };
  }
};

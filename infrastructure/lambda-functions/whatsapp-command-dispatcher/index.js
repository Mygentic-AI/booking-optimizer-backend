const AWS = require('aws-sdk');
const http = require('http');

// Configuration
const EC2_BRIDGE_IP = '40.172.14.214';
const EC2_BRIDGE_PORT = 3000;
const BRIDGE_SECRET = 'default-secret-change-me';

exports.handler = async (event) => {
  console.log('Command Dispatcher received event:', JSON.stringify(event, null, 2));
  
  // Process each SQS message
  const results = [];
  
  for (const record of event.Records) {
    try {
      // Parse SQS message
      const message = JSON.parse(record.body);
      console.log('Processing message:', message);
      
      // Prepare command for EC2 bridge
      const bridgeCommand = {
        requestId: record.messageId,
        userId: 'user001',
        command: message.body?.command || 'getStatus',
        args: message.body?.args || {}
      };
      
      // Send to EC2 bridge via HTTP
      const response = await sendToEC2Bridge(bridgeCommand);
      results.push({
        messageId: record.messageId,
        status: 'success',
        response: response
      });
      
    } catch (error) {
      console.error('Error processing message:', error);
      results.push({
        messageId: record.messageId,
        status: 'error',
        error: error.message
      });
      // Don't throw - we want to process all messages
    }
  }
  
  console.log('Processing results:', results);
  return {
    batchItemFailures: results
      .filter(r => r.status === 'error')
      .map(r => ({ itemIdentifier: r.messageId }))
  };
};

// Function to send command to EC2 bridge
function sendToEC2Bridge(command) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(command);
    
    const options = {
      hostname: EC2_BRIDGE_IP,
      port: EC2_BRIDGE_PORT,
      path: '/api/commands',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-bridge-key': BRIDGE_SECRET,
        'Content-Length': Buffer.byteLength(data)
      }
    };
    
    console.log('Sending to EC2 bridge:', options);
    
    const req = http.request(options, (res) => {
      let responseData = '';
      
      res.on('data', (chunk) => {
        responseData += chunk;
      });
      
      res.on('end', () => {
        console.log('EC2 bridge response:', res.statusCode, responseData);
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(responseData));
          } catch (e) {
            resolve(responseData);
          }
        } else {
          reject(new Error(`EC2 bridge error: ${res.statusCode} - ${responseData}`));
        }
      });
    });
    
    req.on('error', (error) => {
      console.error('EC2 bridge connection error:', error);
      reject(error);
    });
    
    req.write(data);
    req.end();
  });
}
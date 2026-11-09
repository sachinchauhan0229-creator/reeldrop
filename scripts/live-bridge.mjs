process.env.REELDROP_LIVE_BRIDGE = '1';
process.env.PORT = '3040';
process.env.REELDROP_API_PORT ??= '3042';
await import('../dev-server.js');

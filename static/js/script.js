// Placeholder for real-time updates and QR simulation
function fetchMarketData() {
    console.log("Fetching market data...");
    // Add WebSocket or periodic API calls here
}

function simulateQRScan() {
    alert("QR Scan Simulated: Transaction confirmed with Wallet 1");
}

document.addEventListener('DOMContentLoaded', () => {
    fetchMarketData();
    document.querySelectorAll('.qr-simulate').forEach(btn => {
        btn.addEventListener('click', simulateQRScan);
    });
});
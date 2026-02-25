function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body });
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    return errorDiv;
}

function removeErrors() {
    document.querySelectorAll('.error-message').forEach(el => el.remove());
}

function addConnectionStatusHandlers(socket) {
    const statusDiv = document.createElement('div');
    statusDiv.id = 'connectionStatus';
    statusDiv.className = 'connection-status disconnected';
    statusDiv.innerHTML = '<span class="dot"></span><span>Connecting...</span>';
    
    socket.on('connect', () => {
        statusDiv.className = 'connection-status connected';
        statusDiv.innerHTML = '<span class="dot"></span><span>Connected</span>';
        setTimeout(() => statusDiv.remove(), 3000);
    });
    
    socket.on('disconnect', () => {
        statusDiv.className = 'connection-status disconnected';
        statusDiv.innerHTML = '<span class="dot"></span><span>Disconnected - Reconnecting...</span>';
        const container = document.querySelector('.container');
        if (container && !document.getElementById('connectionStatus')) {
            container.insertBefore(statusDiv, container.firstChild);
        }
    });
    
    socket.on('connect_error', (err) => {
        console.error('Connection error:', err);
    });
}

if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}

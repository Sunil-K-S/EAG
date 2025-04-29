// Storage for processed videos
let processedVideos = new Set();
let apiUrl = 'http://localhost:8000/agent';

// Check if backend is available
async function checkBackendStatus() {
    try {
        const response = await fetch(apiUrl, {
            method: 'HEAD',
            timeout: 1000
        });
        return response.ok;
    } catch (error) {
        console.error('Backend not available:', error);
        return false;
    }
}

// Initialize extension
chrome.runtime.onInstalled.addListener(async () => {
    console.log('YouTube RAG Extension installed');
    
    // Initialize processed videos from storage
    try {
        const result = await chrome.storage.local.get('processedVideos');
        if (result.processedVideos) {
            processedVideos = new Set(result.processedVideos);
            console.log('Loaded processed videos from storage:', processedVideos);
        }
    } catch (error) {
        console.error('Error loading from storage:', error);
    }
    
    // Check backend status
    const backendAvailable = await checkBackendStatus();
    console.log('Backend available:', backendAvailable);
});

// Show notification
function showNotification(title, message) {
    try {
        chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon128.png',
            title: title,
            message: message
        });
    } catch (error) {
        console.error('Error showing notification:', error);
    }
}

// Update extension badge
function updateExtensionBadge(text) {
    try {
        chrome.action.setBadgeText({ text });
        if (text === '✓') {
            chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
        } else if (text === '✗') {
            chrome.action.setBadgeBackgroundColor({ color: '#F44336' });
        } else if (text === '⏳') {
            chrome.action.setBadgeBackgroundColor({ color: '#2196F3' });
        }
    } catch (error) {
        console.error('Error updating badge:', error);
    }
}

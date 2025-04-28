// Storage for processed videos
let processedVideos = new Set();
let processingVideos = new Set();
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

// Listen for tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url && tab.url.includes('youtube.com/watch')) {
        console.log('YouTube video page loaded:', tab.url);
        
        try {
            // Extract video ID from URL
            const url = new URL(tab.url);
            const videoId = url.searchParams.get('v');
            
            if (videoId) {
                console.log('Detected video ID:', videoId);
                
                // Check if video is already processed or processing
                if (processedVideos.has(videoId)) {
                    console.log('Video already processed:', videoId);
                } else if (processingVideos.has(videoId)) {
                    console.log('Video is currently being processed:', videoId);
                } else {
                    // Auto-process the video after a short delay
                    setTimeout(() => {
                        console.log('Auto-processing video:', videoId);
                        processVideo(tab.url, videoId);
                    }, 2000);
                }
            }
            
            // Inject content script
            chrome.scripting.executeScript({
                target: { tabId: tabId },
                files: ['content.js']
            }).catch(err => console.error('Error injecting content script:', err));
            
        } catch (error) {
            console.error('Error handling tab update:', error);
        }
    }
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('Background received message:', message);
    
    if (message.action === 'videoChanged') {
        console.log('Video changed:', message.videoId);
        const videoId = message.videoId;
        const url = message.url;
        
        // Check if video is already processed or processing
        if (processedVideos.has(videoId)) {
            console.log('Video already processed:', videoId);
            sendResponse({ status: 'already_processed' });
        } else if (processingVideos.has(videoId)) {
            console.log('Video is currently being processed:', videoId);
            sendResponse({ status: 'processing' });
        } else {
            // Auto-process the video
            processVideo(url, videoId);
            sendResponse({ status: 'processing_started' });
        }
    }
    
    return true;
});

// Process a YouTube video
async function processVideo(url, videoId) {
    if (!url || !videoId || processingVideos.has(videoId) || processedVideos.has(videoId)) {
        return;
    }
    
    console.log(`Starting to process video: ${videoId}`);
    processingVideos.add(videoId);
    
    try {
        // Check if backend is available
        const backendAvailable = await checkBackendStatus();
        if (!backendAvailable) {
            throw new Error('Backend not available');
        }
        
        // Update badge to show processing
        updateExtensionBadge('⏳');
        
        // Call the backend to process the video
        console.log('Sending process request to backend:', url);
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_input: `Process this YouTube video for later search: ${url}`,
                url: url
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Video processing result:', data);
        
        // Check if processing was successful
        if (data.result && typeof data.result === 'string' && 
            (data.result.includes('success') || data.result.includes('chunks'))) {
            // Add to processed videos
            processedVideos.add(videoId);
            
            // Save to storage
            try {
                await chrome.storage.local.set({
                    'processedVideos': Array.from(processedVideos)
                });
                console.log('Saved processed videos to storage');
            } catch (storageError) {
                console.error('Error saving to storage:', storageError);
            }
            
            // Update badge to show success
            updateExtensionBadge('✓');
            
            // Show notification
            showNotification('Video Processed', 'The video has been processed and is ready for search.');
        } else {
            throw new Error('Processing did not return success status');
        }
    } catch (error) {
        console.error('Error processing video:', error);
        // Update badge to show error
        updateExtensionBadge('✗');
        showNotification('Processing Failed', 'Failed to process the video. Please try again.');
    } finally {
        // Remove from processing set
        processingVideos.delete(videoId);
        
        // Reset badge after a delay
        setTimeout(() => {
            updateExtensionBadge('');
        }, 3000);
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

// Handle search queries from popup
async function searchVideo(query, url) {
    if (!query || !url) {
        return { 
            status: "error", 
            message: "Missing query or URL" 
        };
    }
    
    try {
        console.log('Sending search request to backend:', { query, url });
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_input: query,
                url: url
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Search result:', data);
        return data;
    } catch (error) {
        console.error('Error searching video:', error);
        return { 
            status: "error", 
            message: error.message || "Error searching video"
        };
    }
}

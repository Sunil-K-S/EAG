// Log when content script is loaded
console.log('YouTube RAG content script loaded');

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log('Content script received message:', request);
    
    if (request.action === 'seekTo') {
        console.log('Processing seekTo request with time:', request.time);
        
        try {
            // Parse the time properly
            const seekTime = parseFloat(request.time);
            
            if (isNaN(seekTime)) {
                throw new Error(`Invalid time value: ${request.time}`);
            }
            
            // Find the video element with retry mechanism
            let attempts = 0;
            const maxAttempts = 5;
            
            function findAndSeekVideo() {
                attempts++;
                console.log(`Finding video element, attempt ${attempts}/${maxAttempts}`);
                
                // Try to find the video in different ways
                const video = document.querySelector('video') || 
                              document.querySelector('.html5-main-video') ||
                              document.querySelector('.video-stream');
                
                if (video) {
                    console.log('Found video element:', video);
                    console.log('Current video time before seeking:', video.currentTime);
                    
                    // Set both currentTime and use YouTube's API if available
                    video.currentTime = seekTime;
                    
                    // Try to access YouTube's player API
                    try {
                        const ytPlayer = document.querySelector('#movie_player');
                        if (ytPlayer && typeof ytPlayer.seekTo === 'function') {
                            ytPlayer.seekTo(seekTime);
                            console.log('Used YouTube API to seek');
                        }
                    } catch (ytApiError) {
                        console.warn('Could not use YouTube API:', ytApiError);
                    }
                    
                    // Verify the seek worked
                    setTimeout(() => {
                        console.log('Current video time after seeking:', video.currentTime);
                        video.play();
                        console.log('Started video playback');
                        
                        // Send response back to popup
                        sendResponse({
                            success: true, 
                            actualTime: video.currentTime,
                            message: `Successfully seeked to ${seekTime}s`
                        });
                    }, 100);
                    
                    return true;
                } else if (attempts < maxAttempts) {
                    // Retry after a short delay
                    console.log('Video element not found, retrying...');
                    setTimeout(findAndSeekVideo, 300);
                    return true;
                } else {
                    console.error('Failed to find video element after multiple attempts');
                    sendResponse({
                        success: false, 
                        error: 'Could not find video element after multiple attempts'
                    });
                    return false;
                }
            }
            
            return findAndSeekVideo();
        } catch (error) {
            console.error('Error seeking video:', error);
            sendResponse({
                success: false, 
                error: error.message || 'Unknown error while seeking'
            });
            return false;
        }
    }
    
    // Return true to indicate we will send a response asynchronously
    return true;
});

// Function to get current video ID
function getCurrentVideoId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('v');
}

// Function to check if we're on a YouTube video page
function isYouTubeVideoPage() {
    return window.location.hostname === 'www.youtube.com' && 
           window.location.pathname === '/watch' && 
           getCurrentVideoId() !== null;
}

// Notify background script when video changes
let lastVideoId = null;
let lastUrl = null;

function checkVideoChange() {
    if (!isYouTubeVideoPage()) return;
    
    const currentVideoId = getCurrentVideoId();
    const currentUrl = window.location.href;
    
    if (currentVideoId && (currentVideoId !== lastVideoId || currentUrl !== lastUrl)) {
        console.log('Video changed to:', currentVideoId);
        lastVideoId = currentVideoId;
        lastUrl = currentUrl;
        
        // Notify background script
        chrome.runtime.sendMessage({
            action: "videoChanged",
            videoId: currentVideoId,
            url: currentUrl
        }).catch(err => console.warn('Error sending message to background:', err));
    }
}

// Check for video changes regularly
setInterval(checkVideoChange, 1000);

// Check immediately on script load
checkVideoChange(); 
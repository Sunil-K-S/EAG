document.addEventListener('DOMContentLoaded', function() {
    const submitButton = document.getElementById('submitButton');
    const topicInput = document.getElementById('topicInput');
    const queryInput = document.getElementById('queryInput');
    const resultsDiv = document.getElementById('results');
    const statusDiv = document.getElementById('status');

    // Create loading element
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loading';
    loadingDiv.className = 'loading';
    loadingDiv.innerHTML = '<div class="spinner"></div><p>Searching and processing videos...</p>';
    loadingDiv.style.display = 'none';
    document.body.appendChild(loadingDiv);

    // Add CSS for spinner
    const style = document.createElement('style');
    style.textContent = `
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #c00;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);

    async function searchYouTube(topic) {
        try {
            // First, get the cookies and headers
            const response = await fetch('https://www.youtube.com', {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            });

            // Now perform the search with the same headers
            const searchResponse = await fetch(`https://www.youtube.com/results?search_query=${encodeURIComponent(topic)}`, {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://www.youtube.com/'
                }
            });

            if (!searchResponse.ok) {
                throw new Error(`HTTP error! status: ${searchResponse.status}`);
            }

            const html = await searchResponse.text();
            
            // Parse HTML to extract video links
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // Try to find video links in the initial data
            const initialDataMatch = html.match(/var ytInitialData = ({.*?});/);
            if (initialDataMatch) {
                try {
                    const initialData = JSON.parse(initialDataMatch[1]);
                    const videoLinks = extractVideoLinksFromInitialData(initialData);
                    if (videoLinks.length > 0) {
                        return videoLinks.slice(0, 3);
                    }
                } catch (e) {
                    console.warn('Failed to parse initial data:', e);
                }
            }

            // Fallback to DOM parsing if initial data parsing fails
            const videoLinks = Array.from(doc.querySelectorAll('a[href*="/watch?v="]'))
                .map(a => {
                    const href = a.getAttribute('href');
                    if (href && href.includes('/watch?v=')) {
                        const videoId = href.split('v=')[1].split('&')[0];
                        return `https://www.youtube.com/watch?v=${videoId}`;
                    }
                    return null;
                })
                .filter(href => href !== null)
                .filter((value, index, self) => self.indexOf(value) === index)
                .slice(0, 3);

            if (videoLinks.length === 0) {
                throw new Error('No videos found for the given topic');
            }

            return videoLinks;
        } catch (error) {
            console.error('Error searching YouTube:', error);
            throw new Error('Failed to search YouTube: ' + error.message);
        }
    }

    function extractVideoLinksFromInitialData(data) {
        try {
            const videoLinks = [];
            
            // Helper function to traverse the data structure
            function traverse(obj) {
                if (!obj) return;
                
                // Check if this is a video renderer
                if (obj.videoRenderer && obj.videoRenderer.videoId) {
                    videoLinks.push(`https://www.youtube.com/watch?v=${obj.videoRenderer.videoId}`);
                    return;
                }
                
                // Recursively traverse arrays and objects
                if (Array.isArray(obj)) {
                    obj.forEach(item => traverse(item));
                } else if (typeof obj === 'object') {
                    Object.values(obj).forEach(value => traverse(value));
                }
            }
            
            // Start traversal from the root
            traverse(data);
            
            return videoLinks;
        } catch (e) {
            console.error('Error extracting video links from initial data:', e);
            return [];
        }
    }

    async function queryVideo(videoUrl, query) {
        try {
            const response = await fetch('http://localhost:8000/agent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_input: query,
                    url: videoUrl
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error querying video:', error);
            throw new Error(`Failed to query video: ${error.message}`);
        }
    }

    function convertTimestampToSeconds(timestamp) {
        const parts = timestamp.split(':');
        if (parts.length === 2) {
            return parseInt(parts[0]) * 60 + parseInt(parts[1]);
        } else if (parts.length === 3) {
            return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
        }
        return 0;
    }

    function createTimestampLink(videoUrl, timestamp) {
        const seconds = convertTimestampToSeconds(timestamp);
        const url = new URL(videoUrl);
        url.searchParams.set('t', seconds);
        return url.toString();
    }

    function openVideoAtTimestamp(videoUrl, timestamp) {
        const url = createTimestampLink(videoUrl, timestamp);
        chrome.windows.create({
            url: url,
            type: 'normal',
            width: 1280,
            height: 720,
            left: Math.round((screen.width - 1280) / 2),
            top: Math.round((screen.height - 720) / 2)
        });
    }

    function formatResults(videoUrl, results) {
        if (!results || !Array.isArray(results)) {
            return 'No results found';
        }

        return results.map(result => {
            const timestamp = result.timestamp || '00:00';
            const content = result.content || result.text || 'No content available';
            
            return `
                <div class="result-item">
                    <span class="timestamp-link" data-url="${videoUrl}" data-timestamp="${timestamp}">${timestamp}</span>
                    <div class="content">${content}</div>
                </div>
            `;
        }).join('');
    }

    async function getVideoTitle(videoUrl) {
        try {
            const response = await fetch(videoUrl);
            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const title = doc.querySelector('title')?.textContent || videoUrl;
            return title.replace(' - YouTube', '');
        } catch (error) {
            console.error('Error getting video title:', error);
            return videoUrl;
        }
    }

    submitButton.addEventListener('click', async function() {
        const topic = topicInput.value.trim();
        const query = queryInput.value.trim();

        if (!topic || !query) {
            statusDiv.textContent = 'Please enter both a topic and a query.';
            statusDiv.className = 'status error';
            return;
        }

        // Show loading state
        loadingDiv.style.display = 'block';
        resultsDiv.style.display = 'none';
        statusDiv.style.display = 'none';
        submitButton.disabled = true;

        try {
            // Search YouTube for videos
            statusDiv.textContent = 'Searching YouTube...';
            statusDiv.className = 'status';
            statusDiv.style.display = 'block';

            const videoUrls = await searchYouTube(topic);
            if (videoUrls.length === 0) {
                throw new Error('No videos found for the given topic');
            }

            // Clear previous results
            resultsDiv.innerHTML = '';

            // Process each video
            for (const videoUrl of videoUrls) {
                try {
                    // Get video title
                    const videoTitle = await getVideoTitle(videoUrl);
                    
                    // Create video card
                    const videoCard = document.createElement('div');
                    videoCard.className = 'video-card';
                    videoCard.innerHTML = `
                        <div class="video-title">${videoTitle}</div>
                        <div class="video-link">${videoUrl}</div>
                        <div class="video-result">Processing...</div>
                    `;
                    resultsDiv.appendChild(videoCard);

                    // Query the video
                    const result = await queryVideo(videoUrl, query);
                    
                    // Update the video card with results
                    const resultDiv = videoCard.querySelector('.video-result');
                    if (result.result) {
                        try {
                            const resultObj = typeof result.result === 'string' ? 
                                JSON.parse(result.result) : result.result;
                            
                            if (resultObj.results && Array.isArray(resultObj.results)) {
                                resultDiv.innerHTML = formatResults(videoUrl, resultObj.results);
                            } else {
                                resultDiv.textContent = resultObj.message || 'No results found';
                            }
                        } catch (e) {
                            resultDiv.textContent = result.result;
                        }
                    } else {
                        resultDiv.textContent = 'No results found';
                    }
                } catch (error) {
                    console.error(`Error processing video ${videoUrl}:`, error);
                    const videoCard = resultsDiv.lastElementChild;
                    if (videoCard) {
                        const resultDiv = videoCard.querySelector('.video-result');
                        resultDiv.textContent = `Error: ${error.message}`;
                        resultDiv.className = 'video-result error';
                    }
                }
            }

            statusDiv.textContent = 'Search completed';
            statusDiv.className = 'status success';

            // Add event listener for timestamp clicks after results are loaded
            document.querySelectorAll('.timestamp-link').forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    const videoUrl = this.getAttribute('data-url');
                    const timestamp = this.getAttribute('data-timestamp');
                    openVideoAtTimestamp(videoUrl, timestamp);
                });
            });
        } catch (error) {
            console.error('Error:', error);
            resultsDiv.innerHTML = `<p class="error">Error: ${error.message}</p>`;
            statusDiv.textContent = `Error: ${error.message}`;
            statusDiv.className = 'status error';
        } finally {
            loadingDiv.style.display = 'none';
            resultsDiv.style.display = 'block';
            submitButton.disabled = false;
        }
    });

    // Add keyboard support
    [topicInput, queryInput].forEach(input => {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                submitButton.click();
            }
        });
    });
});
